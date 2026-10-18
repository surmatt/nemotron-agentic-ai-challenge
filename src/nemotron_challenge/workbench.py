"""Workbench: run the pipeline stages on one uploaded scan and build views for the visual UI.

Uploaded scans are not part of the pinned 100-scan sample. Their files live apart from the stage
artifacts, in <work_dir>/ui/uploads/<upload_id>/:

    original.<ext>        the uploaded bytes, unchanged
    scan.<jpg|png>        the image sent to Parse (the original, or a converted copy)
    meta.json             file names, checksums, sizes, and any conversion
    state.json            the status of each step
    extract/              raw Parse reply, derived page, entries
    correct/              raw Super VL replies per block, corrected page, entries
    match/                candidates per entry, cached Wikipedia articles, decisions
    compare/              word-frequency comparison of accepted pairs
    failures.jsonl        failed model calls with their error details
    history/<time>/       earlier outputs, moved here when a step runs again

Each step reuses the functions of its pipeline stage. The corpus views only read saved artifacts.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import difflib
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import re
import shutil
import threading
import time
from typing import Any, Callable

from . import compare as compare_stage
from . import correct as correct_stage
from . import extract as extract_stage
from . import match as match_stage
from . import site as site_stage
from .clients import ChatClient, ParseClient, RetrievalClient, ServiceError, WikiClient
from .common import (append_jsonl, read_json, read_jsonl, sha256_bytes, sha256_text, text_dir, utc_now, write_json,
                     write_text)
from .config import EMBED_MODEL, PARSE_MODEL, RERANK_MODEL, SUPER_MODEL, ConfigurationError, Settings
from .data import load_manifest
from .ocr_eval import TEXT_CLASSES, word_list

STEPS = ("extract", "correct", "match", "compare", "document")
NEEDS = {"extract": (), "correct": ("extract",), "match": ("extract",), "compare": ("match",),
         "document": ("extract",)}
STEP_MODELS = {"extract": [PARSE_MODEL], "correct": [SUPER_MODEL],
               "match": ["Wikipedia BM25 API", EMBED_MODEL, RERANK_MODEL], "compare": [], "document": ["LaTeX · tectonic"]}
CORPUS_STAGE = {"document": "site"}
UPLOAD_ID = re.compile(r"[0-9a-f]{12}")
MAX_UPLOAD_BYTES = 30 * 1024 * 1024
PARSE_IMAGE_BYTES = 8 * 1024 * 1024
MAX_SIDE = 10_000
CONVERTED_SIDE = 6_000
EXCERPT_CHARS = 2_000
WORKERS = 4
Progress = Callable[[int, int, str], None]


class StepError(RuntimeError):
    """A step cannot start or did not finish."""


# ---------------------------------------------------------------- uploads


def uploads_root(work_dir: Path) -> Path:
    return work_dir / "ui" / "uploads"


def upload_dir(work_dir: Path, upload_id: str) -> Path:
    if not UPLOAD_ID.fullmatch(upload_id):
        raise StepError("invalid upload ID")
    path = uploads_root(work_dir) / upload_id
    if not (path / "meta.json").is_file():
        raise FileNotFoundError(f"upload {upload_id} does not exist")
    return path


def prepare_image(data: bytes) -> tuple[bytes, str, dict[str, Any]]:
    """Check the upload is an image. Convert it to JPEG when Parse cannot take it as it is."""
    from PIL import Image, UnidentifiedImageError

    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise StepError(f"the file must contain 1 byte to {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB")
    try:
        with Image.open(BytesIO(data)) as probe:
            probe.verify()
        image = Image.open(BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise StepError(f"the file is not a readable image: {exc}") from None
    info = {"format": image.format, "width": image.width, "height": image.height, "converted": False}
    frames = getattr(image, "n_frames", 1)
    if (image.format in {"JPEG", "PNG"} and len(data) <= PARSE_IMAGE_BYTES and max(image.size) <= MAX_SIDE
            and frames == 1):
        return data, "png" if image.format == "PNG" else "jpg", info
    rgb = image.convert("RGB")
    if max(rgb.size) > CONVERTED_SIDE:
        rgb.thumbnail((CONVERTED_SIDE, CONVERTED_SIDE), Image.Resampling.LANCZOS)
    for quality in (92, 85, 75, 65):
        buffer = BytesIO()
        rgb.save(buffer, format="JPEG", quality=quality)
        if buffer.tell() <= PARSE_IMAGE_BYTES:
            break
    else:
        raise StepError("the image stays above 8 MiB after conversion")
    reasons = [r for r, hit in (("format", image.format not in {"JPEG", "PNG"}), ("size", len(data) > PARSE_IMAGE_BYTES),
                                ("dimensions", max(image.size) > MAX_SIDE), ("frames", frames > 1)) if hit]
    info.update({"converted": True, "conversion": {"to": "JPEG", "quality": quality, "reasons": reasons,
                                                   "width": rgb.width, "height": rgb.height}})
    return buffer.getvalue(), "jpg", info


def safe_name(filename: str) -> str:
    name = Path(filename or "scan").name
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:120] or "scan"


def create_upload(work_dir: Path, data: bytes, filename: str, source: dict[str, Any] | None = None) -> str:
    """Store an uploaded scan. The same image bytes give the same upload ID."""
    scan, ext, info = prepare_image(data)
    upload_id = sha256_bytes(scan)[:12]
    folder = uploads_root(work_dir) / upload_id
    if (folder / "meta.json").is_file():
        return upload_id
    folder.mkdir(parents=True, exist_ok=True)
    original_ext = (Path(filename).suffix.lower().lstrip(".") or (info["format"] or "bin").lower())[:8]
    (folder / f"original.{re.sub(r'[^a-z0-9]', '', original_ext) or 'bin'}").write_bytes(data)
    (folder / f"scan.{ext}").write_bytes(scan)
    write_json(folder / "meta.json", {
        "upload_id": upload_id, "filename": safe_name(filename), "uploaded_at": utc_now(),
        "original_sha256": sha256_bytes(data), "original_bytes": len(data),
        "scan_file": f"scan.{ext}", "scan_sha256": sha256_bytes(scan), "scan_bytes": len(scan), "image": info,
        "source": source or {"kind": "upload", "note": "not part of the pinned 100-scan sample"},
    })
    write_json(folder / "state.json", {"steps": {step: {"status": "idle"} for step in STEPS}})
    return upload_id


def create_from_corpus(work_dir: Path, raw_scans: Path, row_index: int) -> str:
    manifest = load_manifest()
    page = next((p for p in manifest["pages"] if p["row_index"] == row_index), None)
    if page is None:
        raise FileNotFoundError(f"row {row_index} is not in the pinned sample")
    data = (raw_scans / page["filename"]).read_bytes()
    if sha256_bytes(data) != page["image_sha256"]:
        raise StepError(f"scan checksum differs: {page['filename']}")
    return create_upload(work_dir, data, page["filename"], {
        "kind": "corpus_copy", "page_id": page["page_id"], "row_index": row_index,
        "image_sha256": page["image_sha256"], "dataset_revision": manifest["revision"],
        "note": "a workbench copy; the stage artifacts of the pinned sample stay unchanged"})


def list_uploads(work_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for meta_file in sorted(uploads_root(work_dir).glob("*/meta.json")):
        meta = read_json(meta_file)
        state = load_state(meta_file.parent)
        rows.append({"id": meta["upload_id"], "filename": meta["filename"], "uploaded_at": meta["uploaded_at"],
                     "source": meta["source"], "steps": {s: state["steps"][s]["status"] for s in STEPS}})
    return sorted(rows, key=lambda r: r["uploaded_at"], reverse=True)


# ---------------------------------------------------------------- state

_STATE_LOCK = threading.Lock()
_RUNNING: dict[str, threading.Thread] = {}


def load_state(folder: Path) -> dict[str, Any]:
    with _STATE_LOCK:
        state = read_json(folder / "state.json")
    for step in STEPS:
        info = state["steps"].setdefault(step, {"status": "idle"})
        if folder.name in _RUNNING:
            continue
        if info["status"] == "running":
            info.update({"status": "failed", "error": "interrupted: the server stopped during this step"})
        elif info["status"] == "queued":
            info["status"] = "idle"
    return state


def update_step(folder: Path, step: str, **values: Any) -> None:
    with _STATE_LOCK:
        state = read_json(folder / "state.json")
        state["steps"].setdefault(step, {}).update(values)
        write_json(folder / "state.json", state)


def reset_step(folder: Path, step: str, status: str = "idle") -> None:
    with _STATE_LOCK:
        state = read_json(folder / "state.json")
        state["steps"][step] = {"status": status}
        write_json(folder / "state.json", state)


def archive_from(folder: Path, step: str) -> str | None:
    """Move the outputs of this step and of every later step to history/<time>/. Reset their status.

    A later step that waits in the queue keeps the status "queued"."""
    later = STEPS[STEPS.index(step):]
    present = [s for s in later if (folder / s).exists()]
    stamp = None
    if present:
        stamp = utc_now().replace(":", "").replace("+0000", "Z")
        target = folder / "history" / stamp
        target.mkdir(parents=True, exist_ok=True)
        for name in present:
            shutil.move(str(folder / name), str(target / name))
        write_json(target / "state.json", load_state(folder))
    statuses = {s: info["status"] for s, info in load_state(folder)["steps"].items()}
    for name in later:
        reset_step(folder, name, "queued" if name != step and statuses[name] == "queued" else "idle")
    return stamp


def blocking_step(state: dict[str, Any], step: str) -> str | None:
    """The earlier step that must finish first, or None."""
    return next((need for need in NEEDS[step] if state["steps"][need]["status"] != "done"), None)


def start(work_dir: Path, upload_id: str, steps: list[str], settings_loader: Callable[[], Settings]) -> list[str]:
    """Run steps in a background thread, in order. Each step must have its earlier steps done or queued."""
    folder = upload_dir(work_dir, upload_id)
    if upload_id in _RUNNING and _RUNNING[upload_id].is_alive():
        raise StepError("a step is already running for this scan")
    state = load_state(folder)
    for step in steps:
        if step not in STEPS:
            raise StepError(f"unknown step: {step}")
        missing = [n for n in NEEDS[step] if state["steps"][n]["status"] != "done" and n not in steps]
        if missing:
            raise StepError(f"run {missing[0]} before {step}")
    for step in steps:
        update_step(folder, step, status="queued")

    def work() -> None:
        try:
            settings = settings_loader()
            for step in steps:
                if blocking_step(load_state(folder), step):
                    reset_step(folder, step, "idle")
                    continue
                run_step(settings, folder, step)
        except (ConfigurationError, OSError) as exc:
            for step in steps:
                if load_state(folder)["steps"][step]["status"] == "queued":
                    update_step(folder, step, status="failed", error=f"{type(exc).__name__}: {exc}")
        finally:
            _RUNNING.pop(upload_id, None)

    thread = threading.Thread(target=work, name=f"workbench-{upload_id}", daemon=True)
    _RUNNING[upload_id] = thread
    thread.start()
    return steps


def remaining_steps(work_dir: Path, upload_id: str) -> list[str]:
    state = load_state(upload_dir(work_dir, upload_id))
    todo = [s for s in STEPS if state["steps"][s]["status"] != "done"]
    return list(STEPS[STEPS.index(todo[0]):]) if todo else list(STEPS)


def run_step(settings: Settings, folder: Path, step: str) -> None:
    """Run one step on an upload. Record the outcome in state.json. Earlier outputs go to history/."""
    archived = archive_from(folder, step)
    started, clock = utc_now(), time.monotonic()
    update_step(folder, step, status="running", started_at=started, archived_previous=archived,
                progress={"done": 0, "total": 0, "label": "starting"})

    def progress(done: int, total: int, label: str) -> None:
        update_step(folder, step, progress={"done": done, "total": total, "label": label})

    try:
        summary = STEP_RUNNERS[step](settings, folder, progress)
        update_step(folder, step, status="done", finished_at=utc_now(),
                    elapsed_seconds=round(time.monotonic() - clock, 2), summary=summary, error=None)
    except Exception as exc:  # noqa: BLE001 - the background thread is the error boundary; record every failure
        error = f"{type(exc).__name__}: {exc}"
        append_jsonl(folder / "failures.jsonl", {"stage": step, "error_type": type(exc).__name__,
                                                  "error": str(exc), "at": utc_now()})
        update_step(folder, step, status="failed", finished_at=utc_now(),
                    elapsed_seconds=round(time.monotonic() - clock, 2), error=error)


# ---------------------------------------------------------------- steps


def upload_page(folder: Path) -> dict[str, Any]:
    """The page record that the extract functions expect, for an uploaded scan."""
    meta = read_json(folder / "meta.json")
    return {"page_id": f"upload:{meta['upload_id']}", "filename": meta["scan_file"], "row_index": 0,
            "volume_id": f"upload:{meta['upload_id']}", "image_sha256": meta["scan_sha256"]}


def step_extract(settings: Settings, folder: Path, progress: Progress) -> dict[str, Any]:
    page = upload_page(folder)
    progress(0, 1, "Parse 3.5 reads the page")
    with ParseClient(settings.parse_base_url, settings.parse_api_key) as client:
        raw = extract_stage.parse_page(client, folder / page["filename"], page, folder / "extract" / "raw.json")
    result = derive_extract(folder, raw)
    progress(1, 1, "segmented")
    return result


def derive_extract(folder: Path, raw: dict[str, Any]) -> dict[str, Any]:
    """Derive the page and its entries from the saved Parse reply in extract/raw.json. Return the step summary."""
    derived = extract_stage.derive_page(upload_page(folder), raw)
    derived["raw_path"] = "extract/raw.json"
    entries = extract_stage.segment([derived])
    write_json(folder / "extract" / "page.json", derived)
    write_json(folder / "extract" / "entries.json", entries)
    return {"model": raw["model"], "parse_seconds": raw["elapsed_seconds"], "finish_reason": derived["finish_reason"],
            "page_status": derived["status"], "blocks": len(derived["blocks"]), "furniture": len(derived["furniture"]),
            "entries": len(entries), "headword_entries": sum(e["start_kind"] == "headword" for e in entries)}


def step_correct(settings: Settings, folder: Path, progress: Progress) -> dict[str, Any]:
    page = read_json(folder / "extract" / "page.json")
    jobs = correct_stage.correction_jobs(page)
    scan = folder / page["filename"]
    records: dict[int, dict[str, Any]] = {}
    failed: list[dict[str, Any]] = []
    done = 0
    lock = threading.Lock()
    progress(0, len(jobs), "Super 3.5 VL corrects block crops")

    def one(block: dict[str, Any]) -> None:
        nonlocal done
        try:
            with ChatClient(settings.super_base_url, settings.super_api_key, settings.super_model) as client:
                record = correct_stage.correct_block(client, correct_stage.DEFAULT_VARIANT, scan, page, block,
                                                     folder / "correct" / "raw" / f"b{block['index']:02d}.json")
            records[block["index"]] = record
        except (ServiceError, ValueError, OSError) as exc:
            failure = {"stage": "correct", "block_index": block["index"], "error_type": type(exc).__name__,
                       "error": str(exc), "at": utc_now()}
            failed.append(failure)
            append_jsonl(folder / "failures.jsonl", failure)
        with lock:
            done += 1
            progress(done, len(jobs), f"block {block['index']}")

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(one, jobs))
    return assemble_correct(folder, page, jobs, records, failed)


def assemble_correct(folder: Path, page: dict[str, Any], jobs: list[dict[str, Any]], records: dict[int, dict[str, Any]],
                     failed: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the corrected page and its entries from the Super VL replies. Return the step summary."""
    corrected, decisions, long_s = correct_stage.assemble_page(page, records, word_list())
    entries = extract_stage.segment([corrected])
    write_json(folder / "correct" / "page.json", corrected)
    write_json(folder / "correct" / "entries.json", entries)
    write_json(folder / "correct" / "failures.json", failed)
    return {"model": SUPER_MODEL, "variant": correct_stage.DEFAULT_VARIANT, "blocks_requested": len(jobs),
            "blocks_corrected": len(records), "blocks_failed": len(failed), "text_decisions": decisions,
            "long_s_rule_changed": long_s, "entries": len(entries)}


def entry_source(folder: Path) -> str:
    return "correct" if (folder / "correct" / "entries.json").is_file() else "extract"


def step_match(settings: Settings, folder: Path, progress: Progress) -> dict[str, Any]:
    source = entry_source(folder)
    entries = read_json(folder / source / "entries.json")
    mode, mode_detail = match_stage.retrieval_mode(settings)
    out = folder / "match"
    selected = [e for e in entries if not match_stage.skip_reason(e)]
    skipped = [{"entry_id": e["entry_id"], "reason": match_stage.skip_reason(e)} for e in entries
               if match_stage.skip_reason(e)]
    done, lock = 0, threading.Lock()
    progress(0, len(selected), f"matching in {mode} mode")

    def one(entry: dict[str, Any]) -> dict[str, Any]:
        nonlocal done
        record = match_stage.match_entry(settings, entry, mode, out, folder / "failures.jsonl")
        with lock:
            done += 1
            progress(done, len(selected), entry["headword"] or entry["entry_id"])
        return record

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        records = list(pool.map(one, selected))
    write_json(out / "matches.json", records)
    write_json(out / "skipped.json", skipped)
    statuses = Counter(r["decision"]["status"] for r in records)
    return {"mode": mode, "mode_detail": mode_detail, "entry_text": source,
            "models": [EMBED_MODEL, RERANK_MODEL] if mode == "model" else [],
            "thresholds": match_stage.model_thresholds() if mode == "model" else {"title_similarity": match_stage.TITLE_ACCEPT},
            "searched": len(records), "skipped": len(skipped), "accepted": statuses["accepted"],
            "rejected": statuses["rejected"], "errors": statuses["error"]}


def step_compare(settings: Settings, folder: Path, progress: Progress) -> dict[str, Any]:
    del settings
    source = entry_source(folder)
    entries = {e["entry_id"]: e for e in read_json(folder / source / "entries.json")}
    accepted = [m for m in read_json(folder / "match" / "matches.json") if m["decision"]["status"] == "accepted"]
    progress(0, len(accepted), "word frequencies and log-odds")
    if not accepted:
        write_json(folder / "compare" / "pairs.json", [])
        return {"pairs": 0, "note": "the match step accepted no pairs, so nothing was compared"}
    articles = {pid: read_json(folder / "match" / "articles" / f"{pid}.json")
                for pid in {m["article"]["page_id"] for m in accepted}}
    compared = compare_stage.compare_matches(entries, accepted, articles)
    pairs = compared["pairs"]
    write_json(folder / "compare" / "pairs.json", pairs)
    log = compared["log"]
    progress(len(accepted), len(accepted), "done")
    return {"method": "word frequencies, log-odds with Dirichlet prior", "entry_text": source, "pairs": len(pairs),
            "mean_top_terms_jaccard": round(sum(p["top_terms_jaccard"] for p in pairs) / len(pairs), 4),
            "mean_frequency_cosine": round(sum(p["frequency_cosine"] for p in pairs) / len(pairs), 4),
            "normalisation_changes": {kind: sum(n for (k, _, _), n in log.items() if k == kind)
                                      for kind in ("abbreviation", "long_s", "historical")},
            "note": "The prior and the reference vocabulary come from the pairs of this scan only."}


def step_document(settings: Settings, folder: Path, progress: Progress) -> dict[str, Any]:
    """Write one LaTeX document for the scan with the site stage code, then compile it with tectonic."""
    del settings
    source = entry_source(folder)
    page = read_json(folder / source / "page.json")
    entries = read_json(folder / source / "entries.json")
    meta = read_json(folder / "meta.json")
    origin = meta["source"]
    if origin.get("kind") == "corpus_copy":
        manifest = load_manifest()
        line = (f"Encyclopaedia Britannica scan, source row {origin['row_index']} "
                f"(workbench copy of {origin['page_id']}).")
    else:
        manifest, line = None, f"Uploaded scan {meta['filename']}. It is not part of the pinned 100-scan sample."
    document = site_stage.latex_document(page, entries, manifest, source_line=line, correction_raw="correct/raw/b*.json")
    out = folder / "document"
    write_text(out / "scan.tex", document)
    progress(0, 1, "tectonic compiles the PDF")
    latex = site_stage.compile_latex(out)
    if latex["failed"]:
        raise StepError(f"tectonic could not compile scan.tex: {latex['failed'][0]['error']}")
    progress(1, 1, "done")
    return {"entry_text": source, "entries": len(entries), "tex_sha256": sha256_text(document),
            "pdf": (out / "scan.pdf").is_file(), "engine": latex["engine"], "note": latex.get("note")}


STEP_RUNNERS: dict[str, Callable[[Settings, Path, Progress], dict[str, Any]]] = {
    "extract": step_extract, "correct": step_correct, "match": step_match, "compare": step_compare,
    "document": step_document}


# ---------------------------------------------------------------- re-runs


def rerun_steps(statuses: dict[str, str], step: str) -> list[str]:
    """The chosen step and every later step that has run, so that the later outputs use the new result."""
    if step not in STEPS:
        raise StepError(f"unknown step: {step}")
    return [step, *(s for s in STEPS[STEPS.index(step) + 1:] if statuses[s] in ("done", "failed"))]


def rerun(work_dir: Path, upload_id: str, step: str, settings_loader: Callable[[], Settings]) -> list[str]:
    state = load_state(upload_dir(work_dir, upload_id))
    return start(work_dir, upload_id, rerun_steps({s: state["steps"][s]["status"] for s in STEPS}, step),
                 settings_loader)


def mark_seeded(work_dir: Path, folder: Path, step: str, source: Path, summary_row: dict[str, Any]) -> None:
    saved = summary(work_dir, step) or {}
    update_step(folder, step, status="done", finished_at=utc_now(), summary=summary_row, error=None,
                seeded_from={"kind": "saved corpus run", "path": str(source), "saved_at": saved.get("finished_at")})


def seed_extract(work_dir: Path, folder: Path, item: dict[str, Any]) -> bool:
    """Reuse the saved Parse reply of the corpus run. The page and entries are derived again for this copy."""
    saved = work_dir / "extract" / "raw" / f"{Path(item['filename']).stem}.json"
    if not saved.is_file() or read_json(folder / "meta.json")["scan_sha256"] != item["image_sha256"]:
        return False
    raw = read_json(saved)
    if raw.get("image_sha256") != item["image_sha256"] or raw.get("model") != PARSE_MODEL:
        return False
    (folder / "extract").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(saved, folder / "extract" / "raw.json")
    mark_seeded(work_dir, folder, "extract", saved, derive_extract(folder, raw))
    return True


def seed_correct(work_dir: Path, folder: Path, item: dict[str, Any]) -> bool:
    """Reuse the saved Super VL replies of the corpus run. The corrected page is assembled again."""
    if text_dir(work_dir).name != "correct":
        return False
    source = work_dir / "correct" / "raw" / correct_stage.DEFAULT_VARIANT
    stem = Path(item["filename"]).stem
    page = read_json(folder / "extract" / "page.json")
    jobs = correct_stage.correction_jobs(page)
    (folder / "correct" / "raw").mkdir(parents=True, exist_ok=True)
    records: dict[int, dict[str, Any]] = {}
    for block in jobs:
        saved = source / f"{stem}-b{block['index']:02d}.json"
        if saved.is_file():
            shutil.copyfile(saved, folder / "correct" / "raw" / f"b{block['index']:02d}.json")
            records[block["index"]] = read_json(saved)
    failed = [{"stage": "correct", "block_index": b["index"], "error": "the corpus run has no saved reply for this block"}
              for b in jobs if b["index"] not in records]
    mark_seeded(work_dir, folder, "correct", source, assemble_correct(folder, page, jobs, records, failed))
    return True


SEEDERS: dict[str, Callable[[Path, Path, dict[str, Any]], bool]] = {"extract": seed_extract, "correct": seed_correct}


def rerun_from_corpus(work_dir: Path, raw_scans: Path, row_index: int, step: str,
                      settings_loader: Callable[[], Settings]) -> dict[str, Any]:
    """Copy a corpus scan into the workbench and re-run one step and the later steps that ran in the corpus.

    The copy reuses the saved outputs of the earlier steps where they exist. The corpus artifacts stay unchanged."""
    corpus = corpus_page(work_dir, row_index, raw_scans)
    statuses = {s: corpus["steps"][s]["status"] for s in STEPS}
    targets = rerun_steps(statuses, step)
    upload_id = create_from_corpus(work_dir, raw_scans, row_index)
    folder = upload_dir(work_dir, upload_id)
    if upload_id in _RUNNING and _RUNNING[upload_id].is_alive():
        raise StepError("a step is already running for this scan")
    needed = set(targets)
    for name in reversed(STEPS):
        if name in needed:
            needed.update(NEEDS[name])
    archive_from(folder, "extract")
    seeded: list[str] = []
    for name in STEPS[:STEPS.index(step)]:
        if (statuses[name] == "done" and all(n in seeded for n in NEEDS[name])
                and name in SEEDERS and SEEDERS[name](work_dir, folder, corpus["meta"])):
            seeded.append(name)
        elif name in needed:
            targets.append(name)
    run = [s for s in STEPS if s in targets]
    return {"id": upload_id, "seeded": seeded, "started": start(work_dir, upload_id, run, settings_loader)}


# ---------------------------------------------------------------- views


def word_diff(before: str, after: str) -> list[dict[str, str]]:
    """Word-level edit operations from the Parse text to the text in use."""
    a, b = before.split(), after.split()
    ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            ops.append({"op": "equal", "text": " ".join(a[i1:i2])})
            continue
        if i2 > i1:
            ops.append({"op": "delete", "text": " ".join(a[i1:i2])})
        if j2 > j1:
            ops.append({"op": "insert", "text": " ".join(b[j1:j2])})
    return ops


def block_view(block: dict[str, Any], correction: dict[str, Any] | None) -> dict[str, Any]:
    parse_text = block.get("parse_text", block["text"])
    row = {"index": block["index"], "cls": block["cls"], "bbox": block["bbox"], "parse_text": parse_text,
           "text": block["text"], "text_source": block.get("text_source"), "review_flag": block.get("review_flag"),
           "super_vl_text": block.get("super_vl_text"), "long_s_rule_changed": block.get("long_s_rule_changed"),
           "eligible_for_correction": block["cls"] in TEXT_CLASSES and bool(parse_text)
           and not correct_stage.box_too_small(block)}
    if block.get("text_source"):
        row["diff"] = word_diff(parse_text, block["text"])
    if correction:
        row["correction"] = {k: correction.get(k) for k in ("model", "elapsed_seconds", "finish_reason", "started_at")}
        row["correction"]["completion_tokens"] = (correction.get("usage") or {}).get("completion_tokens")
    return row


def candidate_view(row: dict[str, Any]) -> dict[str, Any]:
    keep = ("page_id", "revision_id", "title", "url", "best_rank", "bm25", "title_similarity", "context_overlap",
            "cosine", "rerank_logit", "rerank_position")
    return {**{k: row.get(k) for k in keep}, "excerpt": (row.get("excerpt") or "")[:400]}


def article_view(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    article = read_json(path)
    return {**{k: article.get(k) for k in ("page_id", "revision_id", "title", "url", "revision_url", "chars",
                                           "text_sha256", "dataset_revision")},
            "excerpt": article["text"][:EXCERPT_CHARS]}


def search_view(record: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    """Each Wikipedia query with the pages it returned. Runs before the search log rebuild it from the candidates."""
    complete = bool(record.get("searches"))
    if complete:
        searches = [{**s, "hits": [dict(h) for h in s["hits"]]} for s in record["searches"]]
    else:
        variant = record.get("headword_variant")
        searches = [{"id": f"q{i}", "query": q, "kind": match_stage.query_kind(q, record, variant),
                     "hits": sorted(({"page_id": r["page_id"], "title": r["title"], "url": r.get("url"),
                                      "rank": r["bm25"][f"q{i}"]["rank"], "bm25": r["bm25"][f"q{i}"]["score"],
                                      "removed": None} for r in rows if f"q{i}" in r.get("bm25", {})),
                                    key=lambda h: h["rank"])}
                    for i, q in enumerate(record.get("queries") or [])]
    kept = {r["page_id"] for r in rows}
    for search in searches:
        for hit in search["hits"]:
            hit["status"] = "removed" if hit["removed"] else "candidate" if hit["page_id"] in kept else "not_scored"
    return searches, complete


def model_query_view(record: dict[str, Any], entry: dict[str, Any] | None, documents: int) -> dict[str, Any] | None:
    """The text sent to the embedder and the reranker, if the entry text is still the one that was matched."""
    if not record.get("query_chars") or entry is None:
        return None
    same = entry.get("text_sha256") == record.get("entry_text_sha256")
    return {"chars": record["query_chars"], "documents": documents,
            "text": match_stage.query_text(entry)[:record["query_chars"]] if same else None,
            "document_format": f"title, a line break, then the BM25 excerpt (up to {match_stage.EXCERPT_CHARS} characters)",
            "note": None if same else "the entry text changed after this match run"}


def match_view(record: dict[str, Any] | None, candidates_file: Path, articles: Path,
               entry: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if record is None:
        return None
    saved = read_json(candidates_file) if candidates_file.is_file() else {}
    rows = saved.get("candidates", [])
    view = {k: record.get(k) for k in ("mode", "queries", "headword_variant", "candidate_count", "query_chars",
                                       "decision", "list_pages_removed_after_fetch")}
    view["searches"], view["searches_complete"] = search_view({**record, **saved}, rows)
    view["model_query"] = model_query_view(record, entry, len(rows)) if record.get("mode") == "model" else None
    rows = sorted(rows, key=lambda r: (r.get("rerank_position") or 10_000, r.get("best_rank") or 10_000))
    view["candidates"] = [candidate_view(r) for r in rows]
    if record.get("article"):
        view["article"] = article_view(articles / f"{record['article']['page_id']}.json")
    return view


def entry_view(entry: dict[str, Any], page_id: str, match: dict[str, Any] | None,
               pair: dict[str, Any] | None) -> dict[str, Any]:
    return {**{k: entry.get(k) for k in ("entry_id", "headword", "start_kind", "headword_source", "continued",
                                         "chars", "text", "text_sha256")},
            "pages": [{k: p.get(k) for k in ("page_id", "filename", "row_index")} for p in entry["pages"]],
            "block_indexes": [p["block_index"] for p in entry["parts"] if p["page_id"] == page_id],
            "skip_reason": match_stage.skip_reason(entry), "match": match, "pair": pair}


def page_view(page: dict[str, Any], corrections: dict[int, dict[str, Any]]) -> dict[str, Any]:
    return {**{k: page.get(k) for k in ("page_id", "status", "running_header", "header_kind", "header_title",
                                        "page_numbers", "finish_reason", "body_chars", "block_classes")},
            "furniture": [{"index": b["index"], "cls": b["cls"], "bbox": b["bbox"], "text": b["text"]}
                          for b in page["furniture"]],
            "blocks": [block_view(b, corrections.get(b["index"])) for b in page["blocks"]]}


def document_view(tex: Path, base_url: str) -> dict[str, Any] | None:
    """The LaTeX source and the URLs of the .tex and the PDF of one scan, or None before the document exists."""
    if not tex.is_file():
        return None
    pdf = tex.with_suffix(".pdf")
    text = tex.read_text(encoding="utf-8")
    return {"tex": text, "tex_sha256": sha256_text(text), "tex_url": f"{base_url}/document/tex",
            "pdf_url": f"{base_url}/document/pdf" if pdf.is_file() else None,
            "pdf_bytes": pdf.stat().st_size if pdf.is_file() else None, "file": tex.name}


def document_file(work_dir: Path, kind: str, ident: str, ext: str) -> Path:
    if ext not in ("tex", "pdf"):
        raise StepError("the document is a .tex or a .pdf file")
    if kind == "upload":
        path = upload_dir(work_dir, ident) / "document" / f"scan.{ext}"
    else:
        item = next((p for p in load_manifest()["pages"] if str(p["row_index"]) == ident), None)
        if item is None:
            raise FileNotFoundError(f"row {ident} is not in the pinned sample")
        path = work_dir / "site" / "latex" / f"{Path(item['filename']).stem}.{ext}"
    if not path.is_file():
        raise FileNotFoundError(f"no {ext} document for this scan")
    return path


def image_size(path: Path) -> tuple[int, int]:
    from PIL import Image

    with Image.open(path) as image:
        return image.size


def upload_view(work_dir: Path, upload_id: str) -> dict[str, Any]:
    folder = upload_dir(work_dir, upload_id)
    meta, state = read_json(folder / "meta.json"), load_state(folder)
    width, height = image_size(folder / meta["scan_file"])
    view: dict[str, Any] = {
        "id": upload_id, "kind": "upload", "title": meta["filename"], "meta": meta,
        "scan": {"image_url": f"/api/uploads/{upload_id}/image", "width": width, "height": height,
                 "sha256": meta["scan_sha256"], "filename": meta["filename"]},
        "steps": {s: {**state["steps"][s], "models": STEP_MODELS[s], "needs": list(NEEDS[s]),
                      "blocked_by": blocking_step(state, s)} for s in STEPS},
        "running": upload_id in _RUNNING, "page": None, "entries": [], "entry_text": None,
        "document": document_view(folder / "document" / "scan.tex", f"/api/uploads/{upload_id}")
        if state["steps"]["document"]["status"] == "done" else None,
        "failures": read_jsonl(folder / "failures.jsonl") if (folder / "failures.jsonl").is_file() else [],
        "history": sorted(p.name for p in (folder / "history").glob("*")) if (folder / "history").is_dir() else [],
        "crop_url": f"/api/uploads/{upload_id}/blocks/{{index}}/crop",
        "raw_url": f"/api/uploads/{upload_id}/raw/{{step}}",
    }
    done = {s for s in STEPS if state["steps"][s]["status"] == "done"}
    if "extract" not in done:
        return view
    use_correct = "correct" in done
    page = read_json(folder / ("correct" if use_correct else "extract") / "page.json")
    corrections = {int(p.stem[1:]): read_json(p) for p in (folder / "correct" / "raw").glob("b*.json")} \
        if use_correct else {}
    view["page"] = page_view(page, corrections)
    entries = read_json(folder / entry_source(folder) / "entries.json")
    view["entry_text"] = entry_source(folder)
    matches = {m["entry_id"]: m for m in read_json(folder / "match" / "matches.json")} if "match" in done else {}
    pairs = {p["entry_id"]: p for p in read_json(folder / "compare" / "pairs.json")} if "compare" in done else {}
    view["entries"] = [entry_view(e, page["page_id"],
                                  match_view(matches.get(e["entry_id"]),
                                             folder / "match" / "candidates" / f"{e['entry_id']}.json",
                                             folder / "match" / "articles", e),
                                  pairs.get(e["entry_id"])) for e in entries]
    return view


def upload_raw(work_dir: Path, upload_id: str, step: str) -> Any:
    folder = upload_dir(work_dir, upload_id)
    if step == "extract":
        return read_json(folder / "extract" / "raw.json")
    if step == "correct":
        return [read_json(p) for p in sorted((folder / "correct" / "raw").glob("b*.json"))]
    if step == "match":
        return [read_json(p) for p in sorted((folder / "match" / "candidates").glob("*.json"))]
    if step == "compare":
        return read_json(folder / "compare" / "pairs.json")
    if step == "document":
        return {"file": "document/scan.tex", "tex": (folder / "document" / "scan.tex").read_text(encoding="utf-8"),
                "pdf": (folder / "document" / "scan.pdf").is_file()}
    raise StepError(f"unknown step: {step}")


def upload_block(work_dir: Path, upload_id: str, index: int) -> tuple[Path, list[float]]:
    folder = upload_dir(work_dir, upload_id)
    page = read_json(folder / "extract" / "page.json")
    block = next((b for b in page["blocks"] + page["furniture"] if b["index"] == index), None)
    if block is None:
        raise FileNotFoundError(f"block {index} does not exist")
    return folder / page["filename"], block["bbox"]


# ---------------------------------------------------------------- corpus (read only)


@lru_cache(maxsize=32)
def _jsonl_cached(path: str, mtime: float) -> tuple[dict[str, Any], ...]:
    del mtime
    return tuple(read_jsonl(Path(path)))


def jsonl(path: Path) -> list[dict[str, Any]]:
    return list(_jsonl_cached(str(path), path.stat().st_mtime)) if path.is_file() else []


def summary(work_dir: Path, stage: str) -> dict[str, Any] | None:
    path = work_dir / stage / "summary.json"
    return read_json(path) if path.is_file() else None


def corpus_index(work_dir: Path) -> dict[str, Any]:
    manifest = load_manifest()
    pages = {p["page_id"]: p for p in jsonl(text_dir(work_dir) / "pages.jsonl")}
    entries = jsonl(text_dir(work_dir) / "entries.jsonl")
    accepted = {m["entry_id"] for m in jsonl(work_dir / "match" / "matches.jsonl") if m["decision"]["status"] == "accepted"}
    per_page: dict[str, list[str]] = {}
    for entry in entries:
        for p in entry["pages"]:
            per_page.setdefault(p["page_id"], []).append(entry["entry_id"])
    summaries = {s: summary(work_dir, s) for s in ("extract", "correct", "match", "compare", "agent", "site", "evaluate")}
    failed = set((summaries["extract"] or {}).get("failed_scans", []))
    rows = []
    for item in manifest["pages"]:
        page = pages.get(item["page_id"])
        ids = per_page.get(item["page_id"], [])
        rows.append({"row_index": item["row_index"], "page_id": item["page_id"], "filename": item["filename"],
                     "volume_id": item["volume_id"],
                     "status": page["status"] if page else ("parse_failed" if item["page_id"] in failed else "no_run"),
                     "running_header": page["running_header"] if page else None,
                     "entries": len(ids), "accepted": sum(i in accepted for i in ids)})
    return {"dataset": manifest["dataset"], "revision": manifest["revision"], "license": manifest["license"],
            "entry_text": text_dir(work_dir).name, "summaries": summaries, "pages": rows,
            "has_artifacts": any(summaries.values())}


def corpus_page(work_dir: Path, row_index: int, raw_scans: Path = Path("data/raw/britannica")) -> dict[str, Any]:
    manifest = load_manifest()
    item = next((p for p in manifest["pages"] if p["row_index"] == row_index), None)
    if item is None:
        raise FileNotFoundError(f"row {row_index} is not in the pinned sample")
    stem = Path(item["filename"]).stem
    source = text_dir(work_dir)
    page = next((p for p in jsonl(source / "pages.jsonl") if p["page_id"] == item["page_id"]), None)
    summaries = {s: summary(work_dir, CORPUS_STAGE.get(s, s)) for s in STEPS}
    failures = [f for f in jsonl(work_dir / "runs" / "failures.jsonl") if f.get("page_id") == item["page_id"]]
    tex = work_dir / "site" / "latex" / f"{stem}.tex"

    def status(step: str) -> dict[str, Any]:
        info = summaries[step]
        if info is None:
            return {"status": "idle", "models": STEP_MODELS[step], "note": "no saved run of this stage"}
        present = {"extract": page is not None, "correct": source.name == "correct" and page is not None,
                   "document": tex.is_file()}.get(step, True)
        return {"status": "done" if present else ("failed" if step == "extract" and failures else "idle"),
                "finished_at": info.get("finished_at"), "summary": info, "models": STEP_MODELS[step]}

    view: dict[str, Any] = {
        "id": str(row_index), "kind": "corpus", "title": f"Scan {row_index}",
        "meta": {"page_id": item["page_id"], "filename": item["filename"], "image_sha256": item["image_sha256"],
                 "volume_id": item["volume_id"], "dataset": manifest["dataset"], "revision": manifest["revision"]},
        "scan": {"image_url": f"/api/corpus/{row_index}/image", "filename": item["filename"],
                 "sha256": item["image_sha256"]},
        "steps": {s: status(s) for s in STEPS}, "running": False, "page": None, "entries": [],
        "document": document_view(tex, f"/api/corpus/{row_index}"),
        "entry_text": source.name, "failures": failures, "history": [],
        "crop_url": f"/api/corpus/{row_index}/blocks/{{index}}/crop",
        "raw_url": f"/api/corpus/{row_index}/raw/{{step}}",
    }
    raw_scan = raw_scans / item["filename"]
    if raw_scan.is_file():
        view["scan"]["width"], view["scan"]["height"] = image_size(raw_scan)
    if page is None:
        return view
    corrections = {}
    if source.name == "correct":
        for block in page["blocks"]:
            path = work_dir / "correct" / "raw" / correct_stage.DEFAULT_VARIANT / f"{stem}-b{block['index']:02d}.json"
            if path.is_file():
                corrections[block["index"]] = read_json(path)
    view["page"] = page_view(page, corrections)
    matches = {m["entry_id"]: m for m in jsonl(work_dir / "match" / "matches.jsonl")}
    pairs = {p["entry_id"]: p for p in jsonl(work_dir / "compare" / "pairs.jsonl")}
    here = [e for e in jsonl(source / "entries.jsonl") if any(p["page_id"] == item["page_id"] for p in e["pages"])]
    view["entries"] = [entry_view(e, item["page_id"],
                                  match_view(matches.get(e["entry_id"]),
                                             work_dir / "match" / "candidates" / f"{e['entry_id']}.json",
                                             work_dir / "match" / "articles", e),
                                  pairs.get(e["entry_id"])) for e in here]
    return view


def corpus_raw(work_dir: Path, row_index: int, step: str) -> Any:
    view = corpus_page(work_dir, row_index)
    stem = Path(view["meta"]["filename"]).stem
    if step == "extract":
        return read_json(work_dir / "extract" / "raw" / f"{stem}.json")
    if step == "correct":
        folder = work_dir / "correct" / "raw" / correct_stage.DEFAULT_VARIANT
        return [read_json(p) for p in sorted(folder.glob(f"{stem}-b*.json"))]
    ids = [e["entry_id"] for e in view["entries"]]
    if step == "match":
        return [read_json(work_dir / "match" / "candidates" / f"{i}.json") for i in ids
                if (work_dir / "match" / "candidates" / f"{i}.json").is_file()]
    if step == "compare":
        return [p for p in jsonl(work_dir / "compare" / "pairs.jsonl") if p["entry_id"] in ids]
    if step == "document":
        tex = work_dir / "site" / "latex" / f"{stem}.tex"
        return {"file": str(tex), "tex": tex.read_text(encoding="utf-8"), "pdf": tex.with_suffix(".pdf").is_file()}
    raise StepError(f"unknown step: {step}")


def corpus_block(work_dir: Path, raw_scans: Path, row_index: int, index: int) -> tuple[Path, list[float]]:
    view = corpus_page(work_dir, row_index, raw_scans)
    if view["page"] is None:
        raise FileNotFoundError("no saved extract run for this scan")
    block = next((b for b in view["page"]["blocks"] + view["page"]["furniture"] if b["index"] == index), None)
    if block is None:
        raise FileNotFoundError(f"block {index} does not exist")
    return raw_scans / view["meta"]["filename"], block["bbox"]


def corpus_scan(raw_scans: Path, row_index: int) -> Path:
    item = next((p for p in load_manifest()["pages"] if p["row_index"] == row_index), None)
    if item is None:
        raise FileNotFoundError(f"row {row_index} is not in the pinned sample")
    return raw_scans / item["filename"]


# ---------------------------------------------------------------- static site (corpus)

_SITE: dict[str, Any] = {"thread": None, "error": None, "started_at": None}


def site_status(work_dir: Path) -> dict[str, Any]:
    thread = _SITE["thread"]
    return {"running": bool(thread and thread.is_alive()), "started_at": _SITE["started_at"], "error": _SITE["error"],
            "built": (work_dir / "site" / "index.html").is_file(), "summary": summary(work_dir, "site"),
            "url": "/site/index.html"}


def build_site(work_dir: Path, raw_scans: Path, settings_loader: Callable[[], Settings]) -> dict[str, Any]:
    """Run the site stage on the saved corpus artifacts in a background thread."""
    if site_status(work_dir)["running"]:
        raise StepError("the site build is already running")

    def work() -> None:
        try:
            site_stage.run(settings_loader(), work_dir, raw_scans)
        except Exception as exc:  # noqa: BLE001 - the background thread is the error boundary; record every failure
            _SITE["error"] = f"{type(exc).__name__}: {exc}"
            append_jsonl(work_dir / "runs" / "failures.jsonl", {"stage": "site", "error_type": type(exc).__name__,
                                                                 "error": str(exc), "at": utc_now()})

    _SITE.update(error=None, started_at=utc_now(), thread=threading.Thread(target=work, name="site-build", daemon=True))
    _SITE["thread"].start()
    return site_status(work_dir)


def site_file(work_dir: Path, path: str) -> Path:
    root = (work_dir / "site").resolve()
    target = (root / (path or "index.html")).resolve()
    if target.is_dir():
        target = target / "index.html"
    if root not in target.parents or not target.is_file():
        raise FileNotFoundError(f"no site file: {path}")
    return target


# ---------------------------------------------------------------- services

_SERVICE_CACHE: dict[str, Any] = {}
SERVICE_TTL = 60


def services(settings: Settings, live: bool) -> dict[str, Any]:
    """Which services are configured, and (live) whether each answers its catalog or readiness check."""
    configured = {"parse": bool(settings.parse_base_url), "super": bool(settings.super_api_key),
                  "retrieval": bool(settings.retrieval_base_url), "wikipedia": bool(settings.wikipedia_api_url)}
    rows = {name: {"configured": present, "status": "not_tested" if present else "missing"}
            for name, present in configured.items()}
    if not live:
        return {"checked_at": None, "services": rows}
    cached = _SERVICE_CACHE.get("live")
    if cached and time.monotonic() - cached[0] < SERVICE_TTL:
        return cached[1]
    checks = {"parse": lambda: ParseClient(settings.parse_base_url, settings.parse_api_key, timeout=15),
              "super": lambda: ChatClient(settings.super_base_url, settings.super_api_key, settings.super_model,
                                          timeout=15),
              "retrieval": lambda: RetrievalClient(settings.retrieval_base_url, settings.retrieval_api_key, timeout=15),
              "wikipedia": lambda: WikiClient(settings.wikipedia_api_url, timeout=15)}
    operation = {"parse": "verify_model", "super": "verify_model", "retrieval": "verify_models", "wikipedia": "corpus"}

    def check(name: str) -> None:
        if not configured[name]:
            return
        try:
            with checks[name]() as client:
                getattr(client, operation[name])()
            rows[name]["status"] = "ok"
        except (ServiceError, ValueError, ConfigurationError) as exc:
            rows[name].update({"status": "failed", "detail": str(exc)})

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(check, list(checks)))
    result = {"checked_at": utc_now(), "services": rows,
              "scope": "catalog or readiness check; no inference request"}
    _SERVICE_CACHE["live"] = (time.monotonic(), result)
    return result
