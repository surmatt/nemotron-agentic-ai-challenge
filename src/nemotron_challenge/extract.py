"""Extract stage: Parse each scan, keep raw model output, and segment entries.

Method (team choice):
1. Send each verified scan to Parse 3.5 with the default prompt. Save the full reply unchanged.
2. Split the reply into layout blocks with coordinates and classes.
3. Move page headers, page footers, and page numbers out of the entry text.
4. Start a new entry at a block that opens with a capitalised headword (for example "ABBOT, ...").
   Text before the first headword continues an entry from the previous page.
5. Join that continuation to the last entry of the previous page only when the two scans are
   consecutive source rows in the same volume. Otherwise label the entry with the running header.
"""
from __future__ import annotations

import base64
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import time
from typing import Any

from .clients import ParseClient, ServiceError
from .common import (
    append_jsonl, read_json, scan_reference, sha256_bytes, sha256_text, utc_now, with_retry, write_json, write_jsonl,
)
from .config import DEFAULT_PARSE_PROMPT, PARSE_MODEL, Settings
from .contracts import ArtifactRecord
from .data import load_manifest

PARSE_MAX_TOKENS = 8744
BLOCK = re.compile(
    r"<x_([0-9.]+)><y_([0-9.]+)>(.*?)<x_([0-9.]+)><y_([0-9.]+)><class_([A-Za-z-]+)>", re.DOTALL)
FURNITURE = {"Page-header", "Page-footer"}
NON_TEXT = {"Picture"}
# A headword is one or more capitalised words at the start of a block, ended by a comma or full stop.
HEADWORD = re.compile(
    r"^(?P<head>(?:[A-Z][A-Z'’\-]{2,}|ST|MC)(?:[ ,]+(?:of|and|the|de|du|la|le|von|van|y|[A-Z][A-Z'’\-]+))*)\s*[,.;]")
MIN_HEADWORD_LETTERS = 3
# Capitalised words that open structural lines inside an article, not new entries.
NOT_HEADWORDS = {"CHAP", "CHAPTER", "SECT", "SECTION", "PART", "BOOK", "ART", "FIG", "FIGS", "PLATE", "TABLE",
                 "NOTE", "PROP", "PROB", "CASE", "EXAMPLE", "EXAMP", "COR", "SCHOL", "DEF", "AXIOM", "LEMMA",
                 "THEOREM", "SOLUTION", "VOL", "THE", "AND"}


def scan_path(raw_dir: Path, page: dict[str, Any]) -> Path:
    return raw_dir / page["filename"]


def parse_page(client: ParseClient, image: Path, page: dict[str, Any], out: Path) -> dict[str, Any]:
    """Call Parse for one scan and save the unchanged reply with its request settings."""
    data = image.read_bytes()
    if sha256_bytes(data) != page["image_sha256"]:
        raise ValueError(f"scan checksum differs: {image}")
    mime = "png" if image.suffix == ".png" else "jpeg"
    started, clock = utc_now(), time.monotonic()
    reply = with_retry(lambda: client.parse(f"data:image/{mime};base64,{base64.b64encode(data).decode()}",
                                            DEFAULT_PARSE_PROMPT, PARSE_MAX_TOKENS))
    record = {
        "page_id": page["page_id"], "filename": page["filename"], "image_sha256": page["image_sha256"],
        "model": reply.get("model"), "request": {"prompt": DEFAULT_PARSE_PROMPT, "max_tokens": PARSE_MAX_TOKENS},
        "started_at": started, "elapsed_seconds": round(time.monotonic() - clock, 2), "response": reply,
    }
    if record["model"] != PARSE_MODEL:
        raise ValueError(f"Parse reply model differs: {record['model']}")
    write_json(out, record)
    return record


def run_parse(settings: Settings, work_dir: Path, raw_scans: Path, *, workers: int = 4) -> dict[str, Any]:
    """Parse every scan that has no saved reply. Record each failure with its error."""
    manifest = load_manifest()
    raw_dir = work_dir / "extract" / "raw"
    # Parse runs at temperature 0, so a reply that failed the contract fails again. Skip those scans.
    known_failures = {row["page_id"] for row in _failures(work_dir) if row["error_type"] == "ProtocolError"}
    todo = [page for page in manifest["pages"] if page["page_id"] not in known_failures
            and not (raw_dir / f"{Path(page['filename']).stem}.json").is_file()]
    failures: list[dict[str, Any]] = []

    def one(page: dict[str, Any]) -> None:
        out = raw_dir / f"{Path(page['filename']).stem}.json"
        try:
            with ParseClient(settings.parse_base_url, settings.parse_api_key) as client:
                parse_page(client, scan_path(raw_scans, page), page, out)
        except (ServiceError, ValueError, OSError) as exc:
            failure = {"stage": "extract", "page_id": page["page_id"], "filename": page["filename"],
                       "error_type": type(exc).__name__, "error": str(exc), "at": utc_now()}
            failures.append(failure)
            append_jsonl(work_dir / "runs" / "failures.jsonl", failure)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, todo))
    return {"requested": len(todo), "failed": len(failures)}


def _failures(work_dir: Path) -> list[dict[str, Any]]:
    path = work_dir / "runs" / "failures.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []
    return [row for row in rows if row.get("stage") == "extract"]


def parse_blocks(content: str) -> list[dict[str, Any]]:
    blocks = []
    for index, match in enumerate(BLOCK.finditer(content)):
        x0, y0, text, x1, y1, cls = match.groups()
        blocks.append({"index": index, "cls": cls, "bbox": [float(x0), float(y0), float(x1), float(y1)],
                       "text": text.strip()})
    return blocks


def is_page_number(block: dict[str, Any]) -> bool:
    y0, y1 = block["bbox"][1], block["bbox"][3]
    return bool(re.fullmatch(r"[0-9IVXLCivxlc]{1,5}\.?", block["text"])) and (y1 < 0.1 or y0 > 0.9)


def headword(text: str) -> str | None:
    match = HEADWORD.match(text)
    if not match:
        return None
    head = match["head"].strip(" ,")
    if sum(char.isalpha() for char in head) < MIN_HEADWORD_LETTERS or head.split()[0].strip(",") in NOT_HEADWORDS:
        return None
    return head


def classify_header(header: str) -> tuple[str, str | None]:
    """Label a running header as an article title, a dictionary catchword, a plate, or absent.

    Dictionary pages print short catchwords such as "SWI  SYD". Long articles print their title,
    such as "WEIGHTS AND MEASURES." The OCR can space letters ("A R A"), so short words are joined first.
    """
    if not header:
        return "none", None
    if re.search(r"\bplate\b", header, re.IGNORECASE):
        return "plate", None
    header = re.sub(r"\b(?:Part|Chap|Sect)\b.*$", "", header)
    if not any(len(word) >= 5 for word in re.findall(r"[A-Za-z']+", header)):
        return "catchword", None
    if re.search(r"\b[A-Z]\b", header):
        header = re.sub(r"(?<=[A-Z]) (?=[A-Z])", "", header)
    words = re.findall(r"[A-Za-z']+", header)
    title = " ".join(word.upper() for word in words if len(word) >= 2 and not word.islower())
    return "article_title", title or None


def derive_page(page: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    content = raw["response"]["choices"][0]["message"]["content"]
    blocks = parse_blocks(content)
    furniture, body = [], []
    for block in blocks:
        (furniture if block["cls"] in FURNITURE or is_page_number(block) else body).append(block)
    header = " ".join(b["text"] for b in furniture if b["cls"] == "Page-header" and not is_page_number(b)).strip()
    numbers = [b["text"] for b in furniture if is_page_number(b) or re.fullmatch(r"[0-9]+", b["text"])]
    body_chars = sum(len(b["text"]) for b in body if b["cls"] not in NON_TEXT)
    header_kind, header_title = classify_header(header)
    plate = header_kind == "plate" or any(re.search(r"\bplate\b", b["text"], re.IGNORECASE) for b in body[:2])
    status = "ok" if body_chars >= 200 else ("plate" if plate else "blank_or_sparse")
    return {
        "page_id": page["page_id"], "row_index": page["row_index"], "volume_id": page["volume_id"],
        "filename": page["filename"], "image_sha256": page["image_sha256"],
        "raw_path": f"extract/raw/{Path(page['filename']).stem}.json", "raw_content_sha256": sha256_text(content),
        "finish_reason": raw["response"]["choices"][0]["finish_reason"],
        "status": status, "running_header": header, "header_kind": header_kind, "header_title": header_title,
        "page_numbers": numbers, "body_chars": body_chars,
        "block_classes": sorted({b["cls"] for b in blocks}), "furniture": furniture, "blocks": body,
    }


def segment(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group body blocks into entries. Join continuations across consecutive scans of one volume."""
    entries: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for page in sorted(pages, key=lambda p: p["row_index"]):
        if page["status"] != "ok":
            previous = page
            continue
        joinable = (previous is not None and previous["status"] == "ok"
                    and previous["row_index"] + 1 == page["row_index"] and previous["volume_id"] == page["volume_id"])
        current: dict[str, Any] | None = None
        for block in page["blocks"]:
            if block["cls"] in NON_TEXT or not block["text"]:
                continue
            head = headword(block["text"])
            if head is not None:
                current = new_entry(head, "headword", page)
                entries.append(current)
            elif current is None:
                if joinable and entries and entries[-1]["pages"][-1]["page_id"] == previous["page_id"]:
                    current = entries[-1]
                    current["continued"] = True
                else:
                    current = new_entry(page["header_title"], "continuation", page)
                    entries.append(current)
            add_block(current, block, page)
        previous = page
    for number, entry in enumerate(entries, start=1):
        entry["entry_id"] = f"E{number:04d}"
        entry["text"] = "\n\n".join(part["text"] for part in entry["parts"])
        entry["text_sha256"] = sha256_text(entry["text"])
        entry["chars"] = len(entry["text"])
    return entries


def new_entry(head: str | None, kind: str, page: dict[str, Any]) -> dict[str, Any]:
    """A continuation has a headword only when the running header gives the article title."""
    return {"headword": head, "start_kind": kind, "headword_source": "block" if kind == "headword" else (
        "running_header" if head else "unknown"), "continued": False, "pages": [], "parts": []}


def add_block(entry: dict[str, Any], block: dict[str, Any], page: dict[str, Any]) -> None:
    if not entry["pages"] or entry["pages"][-1]["page_id"] != page["page_id"]:
        entry["pages"].append({"page_id": page["page_id"], "filename": page["filename"], "row_index": page["row_index"],
                               "image_sha256": page["image_sha256"], "raw_path": page["raw_path"]})
    entry["parts"].append({"page_id": page["page_id"], "block_index": block["index"], "cls": block["cls"],
                           "bbox": block["bbox"], "text": block["text"]})


def run(settings: Settings, work_dir: Path, raw_scans: Path = Path("data/raw/britannica")) -> dict[str, Any]:
    from .storage import LanceArtifactStore

    manifest = load_manifest()
    missing = [p["filename"] for p in manifest["pages"] if not scan_path(raw_scans, p).is_file()]
    if missing:
        raise FileNotFoundError(f"{len(missing)} scans are missing. Run: uv run nemotron-challenge data fetch")
    parse_run = run_parse(settings, work_dir, raw_scans)
    pages, failed = [], []
    for page in manifest["pages"]:
        raw_file = work_dir / "extract" / "raw" / f"{Path(page['filename']).stem}.json"
        if not raw_file.is_file():
            failed.append(page["page_id"])
            continue
        pages.append(derive_page(page, read_json(raw_file)))
    entries = segment(pages)
    out = work_dir / "extract"
    write_jsonl(out / "pages.jsonl", pages)
    write_jsonl(out / "entries.jsonl", entries)

    store = LanceArtifactStore(settings.db_path)
    by_id = {p["page_id"]: p for p in manifest["pages"]}
    for entry in entries:
        store.put(ArtifactRecord(
            record_id=f"extract:{entry['entry_id']}", stage="extract", artifact_path=str(out / "entries.jsonl"),
            sources=[scan_reference(by_id[p["page_id"]], manifest) for p in entry["pages"]],
            metadata={"headword": entry["headword"], "text_sha256": entry["text_sha256"]},
        ))
    status_counts: dict[str, int] = {}
    for page in pages:
        status_counts[page["status"]] = status_counts.get(page["status"], 0) + 1
    summary = {
        "stage": "extract", "finished_at": utc_now(), "model": PARSE_MODEL,
        "scans": len(manifest["pages"]), "parsed": len(pages), "failed_scans": failed,
        "parse_calls_this_run": parse_run, "page_status": status_counts,
        "incomplete_replies": [p["page_id"] for p in pages if p["finish_reason"] != "stop"],
        "failure_details": {row["page_id"]: row["error"] for row in _failures(work_dir)},
        "entries": len(entries), "headword_entries": sum(e["start_kind"] == "headword" for e in entries),
        "continuation_entries": sum(e["start_kind"] == "continuation" for e in entries),
        "joined_across_pages": sum(len(e["pages"]) > 1 for e in entries),
        "outputs": {"raw": str(out / "raw"), "pages": str(out / "pages.jsonl"), "entries": str(out / "entries.jsonl")},
    }
    write_json(out / "summary.json", summary)
    return summary
