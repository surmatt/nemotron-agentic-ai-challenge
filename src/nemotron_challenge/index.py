"""Index stage: embed source passages with the Nemotron embedder and store them in LanceDB.

Method (team choice):
1. Split each Britannica entry (corrected text when the correct stage has run) and each accepted
   Wikipedia article into passages of about PASSAGE_CHARS characters, cut at whitespace, with overlap.
2. Embed each passage as a document with nvidia/llama-nemotron-embed-vl-1b-v2 (2,048 dimensions).
   A passage whose text checksum is already in the table keeps its stored vector.
3. Write two LanceDB tables, britannica_passages and wikipedia_passages, with the vector, the text,
   and the citation fields (entry and scan IDs, or Wikipedia page and revision IDs).
4. Replace the index records in the provenance table.
Wikipedia articles keep at most MAX_WIKI_PASSAGES passages each; the summary lists cut articles.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from typing import Any

from .clients import RetrievalClient
from .common import read_json, read_jsonl, scan_reference, sha256_text, text_dir, utc_now, wiki_reference, with_retry, write_json
from .config import EMBED_DIMENSIONS, EMBED_MODEL, EMBED_REVISION, Settings
from .contracts import ArtifactRecord
from .data import load_manifest
from .storage import LanceArtifactStore, existing_tables, table_name

PASSAGE_CHARS = 1200
OVERLAP_CHARS = 150
MIN_PASSAGE_CHARS = 80
MAX_WIKI_PASSAGES = 24
BATCH = 16
TABLES = ("britannica_passages", "wikipedia_passages")


def passages(text: str, size: int = PASSAGE_CHARS, overlap: int = OVERLAP_CHARS) -> list[tuple[int, str]]:
    """Split text into (offset, passage) windows that end at whitespace."""
    text = text.strip()
    out, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = text.rfind(" ", start + size // 2, end)
            end = cut if cut > start else end
        chunk = text[start:end].strip()
        if len(chunk) >= MIN_PASSAGE_CHARS or (not out and chunk):
            out.append((start, chunk))
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
        while start < len(text) and not text[start - 1].isspace():
            start += 1
    return out


def britannica_rows(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for entry in entries:
        for number, (offset, text) in enumerate(passages(entry["text"])):
            rows.append({"passage_id": f"{entry['entry_id']}-p{number:02d}", "source": "britannica",
                         "entry_id": entry["entry_id"], "headword": entry["headword"] or "",
                         "scan_page_ids": json.dumps([p["page_id"] for p in entry["pages"]]),
                         "page_id": "", "revision_id": "", "title": entry["headword"] or "", "revision_url": "",
                         "offset": offset, "text": text, "text_sha256": sha256_text(text)})
    return rows


def wikipedia_rows(articles: list[dict[str, Any]], entry_ids: dict[str, list[str]]) -> tuple[list[dict[str, Any]], list[str]]:
    rows, cut = [], []
    for article in articles:
        chunks = passages(article["text"])
        if len(chunks) > MAX_WIKI_PASSAGES:
            cut.append(article["page_id"])
            chunks = chunks[:MAX_WIKI_PASSAGES]
        for number, (offset, text) in enumerate(chunks):
            rows.append({"passage_id": f"W{article['page_id']}-p{number:02d}", "source": "wikipedia",
                         "entry_id": ",".join(entry_ids.get(article["page_id"], [])), "headword": "",
                         "scan_page_ids": "[]", "page_id": article["page_id"], "revision_id": article["revision_id"],
                         "title": article["title"], "revision_url": article["revision_url"],
                         "offset": offset, "text": text, "text_sha256": sha256_text(text)})
    return rows, cut


def stored_vectors(db: Any, name: str) -> dict[str, list[float]]:
    if name not in existing_tables(db):
        return {}
    table = db.open_table(name)
    return {row["text_sha256"]: row["vector"] for row in table.to_arrow().select(["text_sha256", "vector"]).to_pylist()}


def embed_rows(settings: Settings, rows: list[dict[str, Any]], cache: dict[str, list[float]]) -> int:
    """Add a vector to each row. Return the number of passages sent to the embedder."""
    todo = [row for row in rows if row["text_sha256"] not in cache]
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]

    def one(batch: list[dict[str, Any]]) -> None:
        with RetrievalClient(settings.retrieval_base_url, settings.retrieval_api_key) as client:
            vectors = with_retry(lambda: client.embed([{"text": row["text"]} for row in batch], "document"))
        for row, vector in zip(batch, vectors, strict=True):
            cache[row["text_sha256"]] = vector

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(one, batches))
    for row in rows:
        row["vector"] = [float(v) for v in cache[row["text_sha256"]]]
    return len(todo)


def write_table(db: Any, name: str, rows: list[dict[str, Any]]) -> None:
    import pyarrow as pa

    schema = pa.schema([
        ("passage_id", pa.string()), ("source", pa.string()), ("entry_id", pa.string()), ("headword", pa.string()),
        ("scan_page_ids", pa.string()), ("page_id", pa.string()), ("revision_id", pa.string()), ("title", pa.string()),
        ("revision_url", pa.string()), ("offset", pa.int64()), ("text", pa.string()), ("text_sha256", pa.string()),
        ("vector", pa.list_(pa.float32(), EMBED_DIMENSIONS)),
    ])
    db.create_table(name, data=pa.Table.from_pylist(rows, schema=schema), mode="overwrite")


def run(settings: Settings, work_dir: Path) -> dict[str, Any]:
    import lancedb

    if not settings.retrieval_base_url:
        raise ValueError("RETRIEVAL_BASE_URL is not set. The index stage needs the embedder.")
    source = text_dir(work_dir)
    entries = read_jsonl(source / "entries.jsonl")
    matches = [m for m in read_jsonl(work_dir / "match" / "matches.jsonl") if m["decision"]["status"] == "accepted"]
    entry_ids: dict[str, list[str]] = {}
    for m in matches:
        entry_ids.setdefault(m["article"]["page_id"], []).append(m["entry_id"])
    articles = [read_json(work_dir / "match" / "articles" / f"{pid}.json") for pid in sorted(entry_ids)]
    clock = time.monotonic()
    db = lancedb.connect(str(settings.db_path))
    names = {base: table_name(base, work_dir) for base in TABLES}
    b_rows = britannica_rows(entries)
    w_rows, cut = wikipedia_rows(articles, entry_ids)
    cache = {**stored_vectors(db, names["britannica_passages"]), **stored_vectors(db, names["wikipedia_passages"])}
    with RetrievalClient(settings.retrieval_base_url, settings.retrieval_api_key) as client:
        client.verify_models()
    sent = embed_rows(settings, b_rows, cache) + embed_rows(settings, w_rows, cache)
    write_table(db, names["britannica_passages"], b_rows)
    write_table(db, names["wikipedia_passages"], w_rows)

    manifest = load_manifest()
    by_id = {p["page_id"]: p for p in manifest["pages"]}
    counts: dict[str, int] = {}
    for row in b_rows + w_rows:
        key = row["entry_id"] if row["source"] == "britannica" else row["page_id"]
        counts[key] = counts.get(key, 0) + 1
    records = [ArtifactRecord(
        record_id=f"index:britannica:{e['entry_id']}", stage="index", artifact_path=names["britannica_passages"],
        sources=[scan_reference(by_id[p["page_id"]], manifest) for p in e["pages"]],
        metadata={"passages": counts.get(e["entry_id"], 0), "text_sha256": e["text_sha256"]},
    ) for e in entries if counts.get(e["entry_id"])]
    records += [ArtifactRecord(
        record_id=f"index:wikipedia:{a['page_id']}", stage="index", artifact_path=names["wikipedia_passages"],
        sources=[wiki_reference(a)], metadata={"passages": counts.get(a["page_id"], 0), "cut": a["page_id"] in cut},
    ) for a in articles]
    provenance = LanceArtifactStore(settings.db_path, work_dir).replace_stage("index", records)
    summary = {
        "stage": "index", "finished_at": utc_now(), "entry_text": source.name,
        "model": f"{EMBED_MODEL}@{EMBED_REVISION}", "dimensions": EMBED_DIMENSIONS, "db": str(settings.db_path),
        "tables": names, "britannica_passages": len(b_rows), "wikipedia_passages": len(w_rows),
        "wikipedia_articles": len(articles), "articles_cut_at_passages": {"limit": MAX_WIKI_PASSAGES, "page_ids": cut},
        "passages_embedded_this_run": sent, "passages_reused": len(b_rows) + len(w_rows) - sent,
        "seconds": round(time.monotonic() - clock, 1), "provenance": provenance,
    }
    write_json(work_dir / "index" / "summary.json", summary)
    return summary
