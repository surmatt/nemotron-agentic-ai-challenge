"""Correct stage: Super 3.5 VL reads each Parse block image with the Parse text and corrects the text.

Method (team choice):
1. For each running-text block of a scan with status "ok", cut the Parse box from the scan with a small
   margin and enlarge it three times.
2. Send the crop and the Parse text to Super VL. The prompt asks for the corrected text of the region,
   with the same transcription rules as the gold set, and forbids words that the image does not show.
3. Save every reply unchanged. Keep the Parse text next to the corrected text.
4. Keep the Parse text when the box is too small to hold a line (Parse gave the text a wrong box), or
   when the Super VL call failed. Flag blocks that Super VL emptied or made much longer for review:
   a longer text often recovers lines that Parse lost, but the join with the Parse text can be wrong.
5. Apply the dictionary long-s rule to the Super VL text (it sometimes keeps "f" for the long s).
   Keep the Super VL text unchanged next to it.
6. Segment the corrected pages into entries with the extract rules.

Variants compared on the gold set (docs/evaluation/ocr_gold.json):
- crop_nothink: block crop + Parse text, reasoning off (the default for the full run).
- crop_think: block crop + Parse text, reasoning on.
- crop_noparse: block crop only, reasoning off. It shows what the Parse text adds.
- page_nothink: whole page + Parse text + box coordinates, reasoning off.
"""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import time
from typing import Any

from .clients import ChatClient, ServiceError
from .common import append_jsonl, read_json, read_jsonl, scan_reference, utc_now, with_retry, write_json, write_jsonl
from .config import SUPER_MODEL, Settings
from .contracts import ArtifactRecord
from .data import load_manifest
from .extract import segment
from .ocr_eval import TEXT_CLASSES, crop_block, error_rates, fix_long_s, normalise, word_list

# A box narrower or lower than these fractions of the page holds no readable line. Parse sometimes
# gives such a box to a whole paragraph (gold case G21), so the crop cannot show the text.
MIN_BOX_WIDTH = 0.04
MIN_BOX_HEIGHT = 0.008
EXPANDED_RATIO = 1.5
VARIANTS = ("crop_nothink", "crop_think", "crop_noparse", "page_nothink")
DEFAULT_VARIANT = "crop_nothink"
EMPTY = "EMPTY"
RULES = (
    "Rules: write the long s as 's'. Keep the original spelling, capitals, and punctuation. "
    "Join a word that a line-break hyphen splits. Leave out page headers, page numbers, catchwords, "
    "and margin notes. Ignore lines cut at the top or bottom edge of the image. Do not add any word that "
    "you cannot see in the image. Write [?] for an illegible word. "
    f"If the region has no text, answer {EMPTY}. Answer with the text only, with no comments."
)


def instruction(variant: str, block: dict[str, Any]) -> str:
    if variant == "crop_noparse":
        return "Transcribe the text in this image of an 18th- or 19th-century encyclopaedia page region. " + RULES
    where = "The image shows this region of the page." if variant.startswith("crop") else (
        "The image shows the whole page. The region is the box x0={:.3f}, y0={:.3f}, x1={:.3f}, y1={:.3f} "
        "as fractions of the page width and height.".format(*block["bbox"]))
    return ("Correct the OCR text of a region of an 18th- or 19th-century encyclopaedia page. "
            f"{where} Use the image as the authority; the OCR text has many errors. {RULES}\n\n"
            f"OCR text:\n{block['text']}")


def request_body(variant: str, block: dict[str, Any], image: bytes) -> dict[str, Any]:
    data_url = "data:image/jpeg;base64," + base64.b64encode(image).decode()
    think = variant == "crop_think"
    body = {"messages": [{"role": "user", "content": [{"type": "text", "text": instruction(variant, block)},
                                                       {"type": "image_url", "image_url": {"url": data_url}}]}],
            "max_tokens": 12000 if think else 3000, "temperature": 0}
    if not think:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    return body


def image_for(variant: str, scan: Path, block: dict[str, Any]) -> bytes:
    if variant.startswith("crop"):
        return crop_block(scan, block["bbox"])
    from io import BytesIO

    from PIL import Image

    with Image.open(scan) as page:
        buffer = BytesIO()
        page.convert("RGB").save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def correct_block(client: ChatClient, variant: str, scan: Path, page: dict[str, Any], block: dict[str, Any],
                  out: Path) -> dict[str, Any]:
    """Call Super VL for one block, save the unchanged reply, and return the corrected text."""
    if out.is_file():
        return read_json(out)
    body = request_body(variant, block, image_for(variant, scan, block))
    started, clock = utc_now(), time.monotonic()
    reply = with_retry(lambda: client.request("POST", "chat/completions",
                                              payload={"model": client.model, "stream": False, **body}))
    choice = (reply.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content") or ""
    usage = reply.get("usage") or {}
    record = {
        "variant": variant, "page_id": page["page_id"], "block_index": block["index"], "model": reply.get("model"),
        "started_at": started, "elapsed_seconds": round(time.monotonic() - clock, 2),
        "finish_reason": choice.get("finish_reason"), "parse_text": block["text"],
        "corrected_text": "" if content.strip() == EMPTY else content.strip(),
        "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
        "usage": usage, "request": {k: v for k, v in body.items() if k != "messages"},
        "prompt": instruction(variant, block), "response": reply,
    }
    if record["model"] != SUPER_MODEL:
        raise ValueError(f"Super VL reply model differs: {record['model']}")
    if record["finish_reason"] != "stop" or (not content.strip()):
        raise ValueError(f"incomplete Super VL reply: finish_reason={record['finish_reason']}")
    write_json(out, record)
    return record


def box_too_small(block: dict[str, Any]) -> bool:
    x0, y0, x1, y1 = block["bbox"]
    return x1 - x0 < MIN_BOX_WIDTH or y1 - y0 < MIN_BOX_HEIGHT


def decide_text(block: dict[str, Any], record: dict[str, Any] | None, page_ok: bool) -> tuple[str, str | None]:
    """Choose the text for a block and name the reason when Parse text stays."""
    if not page_ok or block["cls"] not in TEXT_CLASSES or not block["text"]:
        return "parse", None
    if box_too_small(block):
        return "parse_fallback", "box_too_small"
    if record is None:
        return "parse_fallback", "super_vl_failed"
    ratio = len(record["corrected_text"]) / max(1, len(block["text"]))
    if ratio > EXPANDED_RATIO and len(record["corrected_text"]) - len(block["text"]) > 40:
        return "super_vl", "expanded_beyond_parse"
    if not record["corrected_text"]:
        return "super_vl", "emptied"
    return "super_vl", None


def raw_path(work_dir: Path, variant: str, page: dict[str, Any], block_index: int) -> Path:
    return work_dir / "correct" / "raw" / variant / f"{Path(page['filename']).stem}-b{block_index:02d}.json"


def correct_workers() -> int:
    """Parallel Super VL calls. Token Factory serves many at once; HTTP 429 replies back off in with_retry."""
    return int(os.environ.get("CHALLENGE_CORRECT_WORKERS", "8"))


def run_blocks(settings: Settings, work_dir: Path, jobs: list[tuple[str, dict[str, Any], dict[str, Any]]],
               raw_scans: Path, workers: int | None = None) -> dict[tuple[str, str, int], dict[str, Any]]:
    """Correct (variant, page, block) jobs in parallel. Record each failure with its error."""
    results: dict[tuple[str, str, int], dict[str, Any]] = {}

    def one(job: tuple[str, dict[str, Any], dict[str, Any]]) -> None:
        variant, page, block = job
        try:
            with ChatClient(settings.super_base_url, settings.super_api_key, settings.super_model) as client:
                record = correct_block(client, variant, raw_scans / page["filename"], page, block,
                                       raw_path(work_dir, variant, page, block["index"]))
            results[(variant, page["page_id"], block["index"])] = record
        except (ServiceError, ValueError, OSError) as exc:
            append_jsonl(work_dir / "runs" / "failures.jsonl", {
                "stage": "correct", "variant": variant, "page_id": page["page_id"], "block_index": block["index"],
                "error_type": type(exc).__name__, "error": str(exc), "at": utc_now()})

    with ThreadPoolExecutor(max_workers=workers or correct_workers()) as pool:
        list(pool.map(one, jobs))
    return results


def evaluate_variants(settings: Settings, work_dir: Path, gold_path: Path,
                      raw_scans: Path = Path("data/raw/britannica")) -> dict[str, Any]:
    """Score Parse and each Super VL variant against the gold transcriptions."""
    gold = read_json(gold_path)["blocks"]
    pages = {p["page_id"]: p for p in read_jsonl(work_dir / "extract" / "pages.jsonl")}
    blocks = {(p["page_id"], b["index"]): b for p in pages.values() for b in p["blocks"]}
    jobs = [(v, pages[g["page_id"]], blocks[(g["page_id"], g["block_index"])]) for v in VARIANTS for g in gold]
    results = run_blocks(settings, work_dir, jobs, raw_scans)
    vocabulary = word_list()
    systems = ("parse", "parse_long_s_rule") + VARIANTS + ("crop_nothink_long_s_rule",)
    rows, empty_cases = [], []
    for g in gold:
        block = blocks[(g["page_id"], g["block_index"])]
        outputs = {"parse": block["text"], "parse_long_s_rule": fix_long_s(block["text"], vocabulary)}
        for variant in VARIANTS:
            record = results.get((variant, g["page_id"], g["block_index"]))
            outputs[variant] = None if record is None else record["corrected_text"]
        crop = outputs["crop_nothink"]
        outputs["crop_nothink_long_s_rule"] = None if crop is None else fix_long_s(crop, vocabulary)
        if g["text"] is None:
            empty_cases.append({"gold_id": g["gold_id"], "outputs_chars": {
                k: (len(normalise(v)) if v is not None else None) for k, v in outputs.items()}})
            continue
        rows.append({"gold_id": g["gold_id"], "row_index": g["row_index"], "block_index": g["block_index"],
                     **{s: (error_rates(g["text"], outputs[s]) if outputs[s] is not None else None) for s in systems}})
    totals = {}
    for system in systems:
        scored = [r[system] for r in rows if r[system] is not None]
        chars = sum(s["ref_chars"] for s in scored)
        words = sum(s["ref_words"] for s in scored)
        totals[system] = {
            "blocks_scored": len(scored), "blocks_missing": len(rows) - len(scored),
            "cer": round(sum(s["char_edits"] for s in scored) / max(1, chars), 4),
            "wer": round(sum(s["word_edits"] for s in scored) / max(1, words), 4),
            "words_not_in_reference_per_100": round(100 * sum(s["words_not_in_reference"] for s in scored)
                                                    / max(1, words), 2),
            "blocks_better_than_parse": None if system == "parse" else sum(
                r[system]["cer"] < r["parse"]["cer"] for r in rows if r[system] is not None),
            "cer_without_G08": round(sum(r[system]["char_edits"] for r in rows if r[system] and r["gold_id"] != "G08")
                                     / max(1, sum(r[system]["ref_chars"] for r in rows
                                                  if r[system] and r["gold_id"] != "G08")), 4),
            "blocks_worse_than_parse": None if system == "parse" else sum(
                r[system]["cer"] > r["parse"]["cer"] for r in rows if r[system] is not None),
        }
    timing = {}
    for variant in VARIANTS:
        records = [r for (v, _, _), r in results.items() if v == variant]
        timing[variant] = {"calls": len(records),
                           "mean_seconds": round(sum(r["elapsed_seconds"] for r in records) / max(1, len(records)), 2),
                           "mean_completion_tokens": round(sum((r["usage"] or {}).get("completion_tokens", 0)
                                                               for r in records) / max(1, len(records)))}
    report = {"stage": "correct-eval", "finished_at": utc_now(), "model": SUPER_MODEL, "gold": str(gold_path),
              "gold_blocks": len(gold), "scored_blocks": len(rows), "totals": totals, "timing": timing,
              "empty_region_cases": empty_cases, "per_block": rows,
              "note": "CER and WER ignore case and accents. Gold made by one transcriber; see the gold file."}
    write_json(work_dir / "correct" / "eval.json", report)
    return report


def correction_jobs(page: dict[str, Any]) -> list[dict[str, Any]]:
    """The blocks of one page that go to Super VL."""
    if page["status"] != "ok":
        return []
    return [b for b in page["blocks"] if b["cls"] in TEXT_CLASSES and b["text"] and not box_too_small(b)]


def assemble_page(page: dict[str, Any], records: dict[int, dict[str, Any]],
                  vocabulary: set[str]) -> tuple[dict[str, Any], dict[str, int], int]:
    """Choose the text of each block of one page. Return the page, the decision counts, and long-s changes."""
    blocks, decisions, long_s_changes = [], {}, 0
    for block in page["blocks"]:
        record = records.get(block["index"])
        source, flag = decide_text(block, record, page["status"] == "ok")
        key = source if not flag else f"{source}+{flag}"
        decisions[key] = decisions.get(key, 0) + 1
        extra = {}
        if source == "super_vl":
            # Super VL sometimes keeps the long s as "f". The dictionary rule repairs what is left.
            text = fix_long_s(record["corrected_text"], vocabulary)
            extra = {"super_vl_text": record["corrected_text"], "long_s_rule_changed": text != record["corrected_text"]}
            long_s_changes += text != record["corrected_text"]
        else:
            text = block["text"]
        blocks.append({**block, "parse_text": block["text"], "text": text, "text_source": source,
                       "review_flag": flag, **extra})
    return {**page, "blocks": blocks}, decisions, long_s_changes


def run(settings: Settings, work_dir: Path, raw_scans: Path = Path("data/raw/britannica"),
        variant: str = DEFAULT_VARIANT) -> dict[str, Any]:
    pages = read_jsonl(work_dir / "extract" / "pages.jsonl")
    wanted = [(p, b) for p in pages if p["status"] == "ok" for b in p["blocks"] if b["cls"] in TEXT_CLASSES and b["text"]]
    jobs = [(variant, p, b) for p in pages for b in correction_jobs(p)]
    results = run_blocks(settings, work_dir, jobs, raw_scans)
    corrected_pages, decisions, long_s_changes, vocabulary = [], {}, 0, word_list()
    by_page: dict[str, dict[int, dict[str, Any]]] = {}
    for (_, page_id, index), record in results.items():
        by_page.setdefault(page_id, {})[index] = record
    for page in pages:
        corrected, counts, changed = assemble_page(page, by_page.get(page["page_id"], {}), vocabulary)
        corrected_pages.append(corrected)
        long_s_changes += changed
        for key, count in counts.items():
            decisions[key] = decisions.get(key, 0) + count
    entries = segment(corrected_pages)
    out = work_dir / "correct"
    write_jsonl(out / "pages.jsonl", corrected_pages)
    write_jsonl(out / "entries.jsonl", entries)
    from .storage import LanceArtifactStore

    manifest = load_manifest()
    by_id = {p["page_id"]: p for p in manifest["pages"]}
    sources_by_block = {(p["page_id"], b["index"]): b.get("text_source", "parse")
                        for p in corrected_pages for b in p["blocks"]}
    provenance = LanceArtifactStore(settings.db_path, work_dir).replace_stage("correct", (ArtifactRecord(
        record_id=f"correct:{entry['entry_id']}", stage="correct", artifact_path=str(out / "entries.jsonl"),
        sources=[scan_reference(by_id[p["page_id"]], manifest) for p in entry["pages"]],
        metadata={"headword": entry["headword"], "text_sha256": entry["text_sha256"], "model": SUPER_MODEL,
                  "variant": variant, "text_sources": sorted({sources_by_block.get((part["page_id"], part["block_index"]),
                                                                                   "parse") for part in entry["parts"]})},
    ) for entry in entries))
    evaluation = out / "eval.json"
    summary = {
        "stage": "correct", "finished_at": utc_now(), "model": SUPER_MODEL, "variant": variant,
        "provenance": provenance,
        "text_blocks": len(wanted), "blocks_requested": len(jobs), "blocks_corrected": len(results),
        "blocks_failed": len(jobs) - len(results), "text_decisions": decisions,
        "post_process": {"long_s_rule": "ocr_eval.fix_long_s with the system word list", "blocks_changed": long_s_changes},
        "entries": len(entries), "entries_from_parse_only": len(read_jsonl(work_dir / "extract" / "entries.jsonl")),
        "gold_evaluation": read_json(evaluation)["totals"] if evaluation.is_file() else None,
        "outputs": {"raw": str(out / "raw" / variant), "pages": str(out / "pages.jsonl"),
                    "entries": str(out / "entries.jsonl")},
    }
    write_json(out / "summary.json", summary)
    return summary
