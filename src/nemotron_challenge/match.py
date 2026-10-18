"""Match stage: find Wikipedia candidates for each Britannica entry and decide on a match.

Method (team choice):
1. Skip entries with fewer than MIN_ENTRY_CHARS characters, and continuations without a known
   title and fewer than MIN_UNTITLED_CHARS characters. Record each skip.
2. Search the shared BM25 index with up to four queries: the headword, an OCR headword variant when
   one exists, the headword with the 6 most frequent dictionary words of the whole entry text and the
   running headers (long s repaired first), and the Super VL title guess with its
   terms (terms.py). An entry without a headword uses the keywords only for the third query.
   A failed or missing Super VL call removes only the fourth query.
3. Score the merged candidates:
   - model mode (retrieval service ready): Nemotron embedder cosine between the entry text and
     each candidate (title + excerpt), then Nemotron reranker raw logits on the same pairs.
     Accept the reranker's first candidate when its logit, cosine, and title similarity pass the
     thresholds in docs/evaluation/match_thresholds.json. The runner-up's score does not affect acceptance.
     calibrate.py fits them on 60 hand-labelled entries (docs/evaluation/match-calibration.md).
     The current cosine threshold is 0.15; the title test is off. Legacy margin thresholds are ignored.
     Without the file, the first GPU-run rule applies: logit >= RERANK_ACCEPT (-6.0) and title
     similarity >= MODEL_TITLE_ACCEPT (0.75). Raw logits on OCR text were mostly negative (median -6.1).
   - lexical mode (no retrieval service): accept the candidate whose title matches the headword
     (similarity >= TITLE_ACCEPT). Prefer a plain title to one with a qualifier in brackets.
     Reject titles of modern media (albums, films, magazines), name pages, and numbered objects. Record the excerpt vocabulary overlap.
     The record labels these matches "provisional_lexical".
   Disambiguation pages and list pages ("X may refer to: ...") are removed from the candidates,
   also when the title has no "(disambiguation)" qualifier. The full text of an accepted article is
   checked again, and a list page there sends the decision to the next candidate.
5. OCR-tolerant headword: a headword word of HEADWORD_VARIANT_MIN letters or more that is not in the
   system word list gets a variant when exactly one dictionary word is close (ratio >= HEADWORD_VARIANT_RATIO),
   for example PHILLOOGY -> philology. The variant adds one search and counts for title similarity.
4. Read the full text of each accepted article, verify its checksum, and cache it with its revision.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import difflib
from pathlib import Path
import re
from typing import Any

from . import terms as terms_stage
from .clients import ChatClient, RetrievalClient, ServiceError, WikiClient
from .common import (
    text_dir,
    append_jsonl, read_json, read_jsonl, scan_reference, sha256_text, system_words, utc_now, wiki_reference,
    with_retry, write_json, write_jsonl,
)
from .config import EMBED_MODEL, RERANK_MODEL, SUPER_MODEL, WIKIPEDIA_REVISION, Settings
from .ocr_eval import fix_long_s
from .contracts import ArtifactRecord
from .data import load_manifest

MIN_ENTRY_CHARS = 150
MIN_UNTITLED_CHARS = 500
TOP_K = 20
EXCERPT_CHARS = 1200
TITLE_ACCEPT = 0.85
# Modern media titles, name lists, and numbered objects (minor planets such as "342 Endymion") share
# names with old topics but cannot describe them.
MEDIA_QUALIFIER = re.compile(
    r"\((?:[^)]*\b)?(?:album|song|single|film|band|magazine|journal|novel|TV series|television|EP|video game|"
    r"comics|play|opera|musical|manga|anime|character|rapper|singer|newspaper|company|ship|surname|given name|"
    r"name|artist|musician|footballer|wrestler|horse)\b[^)]*\)|^\d", re.IGNORECASE)
# A list page names other articles. It cannot support a topic comparison.
LIST_PAGE = re.compile(r"\b(?:may|might|can|could) (?:also )?refer to\b", re.IGNORECASE)
LIST_PAGE_HEAD_CHARS = 600
HEADWORD_VARIANT_MIN = 6
HEADWORD_VARIANT_RATIO = 0.85
MAX_DECISIONS = 3
# Fallback thresholds for model mode when docs/evaluation/match_thresholds.json is absent.
# They come from the first GPU run (raw logits mostly negative on OCR text, median -6.1).
RERANK_ACCEPT = -6.0
MODEL_TITLE_ACCEPT = 0.75
COSINE_ACCEPT = 0.0
QUERY_TEXT_CHARS = 1500
FREQUENCY_KEYWORDS = 6
STOPWORDS = set("""
a about above after again against all also am an and any are as at be because been before being below between
both but by can could did do does doing down during each either else ever every few for from further had has have
having he her here hers him his how however i if in into is it its itself just least less many may might more most
much must my neither no nor not now of off on once one only or other ought our ours out over own same shall she
should since so some such than that the their theirs them then there therefore these they this those though thus
to too under until up upon very was we were what when where whether which while who whom whose why will with
within without would yet you your viz etc called likewise wherein whereof hath doth also two three first second
""".split())


def words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 3 and w not in STOPWORDS]


def keyword_source(entry: dict[str, Any], pages: dict[str, dict[str, Any]] | None = None) -> str:
    """The text the frequency keywords come from: headword, running headers, and the entry text."""
    headers = [(pages.get(p["page_id"]) or {}).get("running_header") or "" for p in entry.get("pages", [])] \
        if pages else []
    return " ".join([entry.get("headword") or "", *headers, entry["text"]])


def keywords(text: str, limit: int = FREQUENCY_KEYWORDS,
             vocabulary: frozenset[str] | set[str] | None = None) -> list[str]:
    """The most frequent dictionary words of length >= 4. No dictionary means no filter."""
    vocabulary = system_words() if vocabulary is None else vocabulary
    if vocabulary:
        text = fix_long_s(text, vocabulary)
    counts = Counter(w for w in words(text) if len(w) >= 4 and (not vocabulary or w in vocabulary))
    return [word for word, _ in counts.most_common(limit)]


def norm_title(text: str) -> str:
    text = re.sub(r"\(.*?\)", "", text).lower()
    text = re.sub(r"[^a-z ]", " ", text)
    return " ".join(w[:-1] if len(w) > 4 and w.endswith("s") else w for w in text.split())


def stem(word: str) -> str:
    for suffix in ("ings", "ing", "ancy", "ency", "ant", "ent", "ies", "es", "ed", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def title_similarity(headword: str | None, title: str) -> float:
    """Compare the headword with the title, without parenthetical qualifiers, as words and as stems."""
    if not headword:
        return 0.0
    a, b = norm_title(headword), norm_title(title)
    plain = difflib.SequenceMatcher(None, a, b).ratio()
    stems = difflib.SequenceMatcher(None, " ".join(map(stem, a.split())), " ".join(map(stem, b.split()))).ratio()
    return round(max(plain, stems), 4)


def context_overlap(entry_words: set[str], excerpt: str) -> float:
    """Share of the candidate excerpt vocabulary that also occurs in the entry text."""
    candidate = set(words(excerpt))
    return round(len(entry_words & candidate) / len(candidate), 4) if candidate else 0.0


def clean_headword(headword: str | None) -> str:
    return " ".join(re.sub(r"[^A-Za-z' -]", " ", headword or "").lower().split())


def headword_variant(headword: str | None, vocabulary: frozenset[str] | set[str] | None = None) -> str | None:
    """Replace OCR-damaged headword words with their only close dictionary word. None if nothing changes."""
    vocabulary = system_words() if vocabulary is None else vocabulary
    if not vocabulary:
        return None
    changed, result = False, []
    for word in clean_headword(headword).split():
        if len(word) >= HEADWORD_VARIANT_MIN and word not in vocabulary:
            pool = [w for w in vocabulary if w[:1] == word[:1] and abs(len(w) - len(word)) <= 2]
            close = difflib.get_close_matches(word, pool, n=2, cutoff=HEADWORD_VARIANT_RATIO)
            if len(close) == 1:
                word, changed = close[0], True
        result.append(word)
    return " ".join(result) if changed else None


def is_list_page(text: str) -> bool:
    return bool(LIST_PAGE.search(text[:LIST_PAGE_HEAD_CHARS]))


def llm_query(llm: dict[str, Any], head: str, variant: str | None) -> str | None:
    """The q3 query from a Super VL terms result: title guess (or headword) plus the terms."""
    if not llm or llm.get("status") != "ok" or not (llm.get("title") or llm.get("terms")):
        return None
    seen, kept = set(), []
    for word in " ".join([llm.get("title") or variant or head, *(llm.get("terms") or [])]).split():
        if word.lower() not in seen:
            seen.add(word.lower())
            kept.append(word)
    return " ".join(kept[:64])[:512] if kept else None


def queries(entry: dict[str, Any], variant: str | None = None, *, pages: dict[str, dict[str, Any]] | None = None,
            llm: dict[str, Any] | None = None) -> list[tuple[str, str]]:
    """The BM25 queries of one entry as (query, kind) pairs, at most 64 words and 512 characters."""
    head = clean_headword(entry["headword"])
    keys = [k for k in keywords(keyword_source(entry, pages)) if k not in head.split()]
    result = []
    if head:
        result.append((head, "headword"))
    if variant and variant != head:
        result.append((variant, "OCR headword variant"))
    combined = " ".join([variant or head] + keys).strip()
    if combined and combined not in [q for q, _ in result]:
        result.append((" ".join(combined.split()[:64])[:512],
                       "headword + keywords" if head else "keywords"))
    extra = llm_query(llm or {}, head, variant)
    if extra and extra not in [q for q, _ in result]:
        result.append((extra, "LLM title + terms"))
    return result


def removal_reason(title: str, excerpt_offset: int, excerpt: str) -> str | None:
    if "(disambiguation)" in title:
        return "disambiguation page"
    if excerpt_offset == 0 and is_list_page(excerpt):
        return "list page"
    return None


def query_kind(query: str, entry: dict[str, Any], variant: str | None) -> str:
    if query == clean_headword(entry["headword"]):
        return "headword"
    if variant and query == variant:
        return "OCR headword variant"
    return "headword + keywords" if clean_headword(entry["headword"]) else "keywords"


def candidates(wiki: WikiClient, entry: dict[str, Any],
               searches: list[dict[str, Any]] | None = None, *,
               pages: dict[str, dict[str, Any]] | None = None,
               llm: dict[str, Any] | None = None) -> tuple[list[str], list[dict[str, Any]]]:
    """Merge BM25 hits of all queries. Remove disambiguation pages and list pages.

    When `searches` is a list, append each query with every hit it returned, in rank order."""
    merged: dict[str, dict[str, Any]] = {}
    variant = headword_variant(entry["headword"])
    pairs = queries(entry, variant, pages=pages, llm=llm)
    used = [q for q, _ in pairs]
    for query_index, (query, kind) in enumerate(pairs):
        result = with_retry(lambda: wiki.search(query, top_k=TOP_K, excerpt_chars=EXCERPT_CHARS))
        if searches is not None:
            searches.append({"id": f"q{query_index}", "query": query, "kind": kind,
                             "top_k": TOP_K, "excerpt_chars": EXCERPT_CHARS,
                             "hits": [{"page_id": h.page_id, "title": h.title, "url": h.url, "rank": h.rank,
                                       "bm25": round(h.bm25_score, 4),
                                       "removed": removal_reason(h.title, h.excerpt_offset, h.excerpt)}
                                      for h in result.hits]})
        for hit in result.hits:
            row = merged.setdefault(hit.page_id, {
                "page_id": hit.page_id, "revision_id": hit.revision_id, "title": hit.title, "url": hit.url,
                "excerpt": hit.excerpt, "excerpt_offset": hit.excerpt_offset, "total_chars": hit.total_chars,
                "bm25": {}, "best_rank": hit.rank,
            })
            row["bm25"][f"q{query_index}"] = {"rank": hit.rank, "score": round(hit.bm25_score, 4)}
            row["best_rank"] = min(row["best_rank"], hit.rank)
    rows = sorted((r for r in merged.values() if not removal_reason(r["title"], r["excerpt_offset"], r["excerpt"])),
                  key=lambda r: r["best_rank"])
    entry_words = set(words(entry["text"]))
    for row in rows:
        row["title_similarity"] = max(title_similarity(entry["headword"], row["title"]),
                                      title_similarity(variant, row["title"]))
        row["context_overlap"] = context_overlap(entry_words, row["excerpt"])
    return used, rows


def query_text(entry: dict[str, Any]) -> str:
    head = entry["headword"] or ""
    body = re.sub(r"\s+", " ", entry["text"]).strip()
    text = f"{head}. {body}" if head else body
    return text[:QUERY_TEXT_CHARS]


def document_text(row: dict[str, Any]) -> str:
    return f"{row['title']}\n{row['excerpt']}"[:8000]


QUERY_FALLBACK_CHARS = (700, 300)


def model_scores(retrieval: RetrievalClient, entry: dict[str, Any], rows: list[dict[str, Any]]) -> int:
    """Add embedder cosine and reranker logits to each candidate row. Return the query length used.

    The embedder accepts 512 query tokens. Text full of numbers can pass that limit in 1,500 characters,
    and the service answers HTTP 422. Then the query is shortened and sent again.
    """
    rows[:] = rows[:32]
    for limit in (QUERY_TEXT_CHARS, *QUERY_FALLBACK_CHARS):
        query = query_text(entry)[:limit]
        try:
            [query_vector] = with_retry(lambda: retrieval.embed([query], "query"))
            ranked = with_retry(lambda: retrieval.rerank(query, [document_text(r) for r in rows]))
            break
        except ServiceError as exc:
            if exc.status_code != 422 or limit == QUERY_FALLBACK_CHARS[-1]:
                raise
    for start in range(0, len(rows), 16):
        batch = rows[start:start + 16]
        vectors = with_retry(lambda: retrieval.embed([{"text": document_text(r)} for r in batch], "document"))
        for row, vector in zip(batch, vectors, strict=True):
            row["cosine"] = round(sum(a * b for a, b in zip(query_vector, vector)), 6)
    for position, result in enumerate(ranked, start=1):
        rows[result["index"]]["rerank_logit"] = round(result["relevance_score"], 6)
        rows[result["index"]]["rerank_position"] = position
    return len(query)


THRESHOLD_FILE = Path(__file__).resolve().parents[2] / "docs" / "evaluation" / "match_thresholds.json"


def model_thresholds() -> dict[str, float]:
    """Load the absolute score thresholds, ignoring legacy margin values, or use the defaults."""
    if THRESHOLD_FILE.is_file():
        data = read_json(THRESHOLD_FILE)
        return {"rerank_logit": data["rerank_logit"], "cosine": data["cosine"],
                "title_similarity": data.get("title_similarity", 0.0)}
    return {"rerank_logit": RERANK_ACCEPT, "cosine": COSINE_ACCEPT,
            "title_similarity": MODEL_TITLE_ACCEPT}


def decide(entry: dict[str, Any], rows: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    if not rows:
        return {"status": "rejected", "reason": "no BM25 candidates"}
    if mode == "model":
        best = min(rows, key=lambda r: r["rerank_position"])
        # Keep the score gap as diagnostic evidence, not an acceptance threshold.
        others = sorted((r["rerank_logit"] for r in rows if r is not best), reverse=True)
        margin = round(best["rerank_logit"] - others[0], 6) if others else None
        evidence = {"page_id": best["page_id"], "title": best["title"], "rerank_logit": best["rerank_logit"],
                    "cosine": best["cosine"], "margin_to_next": margin, "title_similarity": best["title_similarity"]}
        limits = model_thresholds()
        if (best["rerank_logit"] >= limits["rerank_logit"]
                and best["cosine"] >= limits["cosine"] and best["title_similarity"] >= limits["title_similarity"]):
            return {"status": "accepted", "method": "nemotron_embed_rerank", "thresholds": limits, **evidence}
        failed = [f"{key} {best[key]:.6f} < {limit:g}" for key, limit in limits.items()
                  if best[key] < limit]
        return {"status": "rejected", "method": "nemotron_embed_rerank", "thresholds": limits,
                "reason": "; ".join(failed),
                **evidence}
    eligible = [r for r in rows if not MEDIA_QUALIFIER.search(r["title"])]
    best = max(eligible or rows, key=lambda r: (
        r["title_similarity"] >= TITLE_ACCEPT, "(" not in r["title"], r["title_similarity"],
        r["context_overlap"], -r["best_rank"]))
    evidence = {"page_id": best["page_id"], "title": best["title"], "title_similarity": best["title_similarity"],
                "context_overlap": best["context_overlap"], "bm25_best_rank": best["best_rank"]}
    if best["title_similarity"] >= TITLE_ACCEPT and not MEDIA_QUALIFIER.search(best["title"]):
        return {"status": "accepted", "method": "provisional_lexical", **evidence}
    return {"status": "rejected", "method": "provisional_lexical",
            "reason": f"no candidate with title similarity >= {TITLE_ACCEPT} outside media titles", **evidence}


def fetch_article(wiki: WikiClient, page_id: str, cache: Path) -> dict[str, Any]:
    path = cache / f"{page_id}.json"
    if path.is_file():
        return read_json(path)
    parts, offset, first = [], 0, None
    while offset is not None:
        part = with_retry(lambda: wiki.article(page_id, offset=offset, max_chars=20000))
        first = first or part
        parts.append(part.text)
        offset = part.next_offset
    text = "".join(parts)
    if sha256_text(text) != first.provenance.text_sha256:
        raise ValueError(f"article {page_id} text checksum differs")
    article = {
        "page_id": first.page_id, "revision_id": first.revision_id, "title": first.title, "url": first.url,
        "revision_url": first.provenance.revision_url, "dataset_revision": first.provenance.dataset_revision,
        "text_sha256": first.provenance.text_sha256, "license": first.license, "chars": len(text), "text": text,
    }
    write_json(path, article)
    return article


def finish_match(wiki: WikiClient, entry: dict[str, Any], rows: list[dict[str, Any]],
                 record: dict[str, Any], out: Path) -> None:
    """Decide from scored candidates and fetch the selected article before accepting it."""
    record.pop("article", None)
    record.setdefault("list_pages_removed_after_fetch", [])
    remaining = list(rows)
    for _ in range(MAX_DECISIONS):
        record["decision"] = decide(entry, remaining, record["mode"])
        if record["decision"]["status"] != "accepted":
            break
        article = fetch_article(wiki, record["decision"]["page_id"], out / "articles")
        if not is_list_page(article["text"]):
            record["article"] = {k: article[k] for k in (
                "page_id", "revision_id", "title", "url", "revision_url", "text_sha256", "chars")}
            break
        record["list_pages_removed_after_fetch"].append(
            {"page_id": article["page_id"], "title": article["title"]})
        remaining = [r for r in remaining if r["page_id"] != article["page_id"]]
    else:
        record["decision"] = {"status": "rejected", "method": record["decision"].get("method"),
                              "reason": f"{MAX_DECISIONS} accepted candidates were list pages"}
    write_json(out / "candidates" / f"{entry['entry_id']}.json", {**record, "candidates": rows})


def validate_saved_scores(entry: dict[str, Any], saved: dict[str, Any]) -> None:
    if saved.get("entry_id") != entry["entry_id"] or saved.get("entry_text_sha256") != entry["text_sha256"]:
        raise ValueError("entry text differs from the saved scores; re-run Match")
    if saved.get("mode") != "model" or saved.get("decision", {}).get("status") == "error":
        raise ValueError("a completed model match run is required; re-run Match")
    if "candidates" not in saved or any(
            not {"rerank_position", "rerank_logit", "cosine", "title_similarity"} <= row.keys()
            for row in saved["candidates"]):
        raise ValueError("saved candidates have no model scores; re-run Match")


def reapply_entry(settings: Settings, entry: dict[str, Any], saved: dict[str, Any],
                  out: Path, failures: Path) -> dict[str, Any]:
    """Apply the current rule to saved scores. Do not search or call any model."""
    validate_saved_scores(entry, saved)
    record = {k: v for k, v in saved.items() if k != "candidates"}
    record["decision_reapplied_at"] = utc_now()
    try:
        with WikiClient(settings.wikipedia_api_url) as wiki:
            finish_match(wiki, entry, saved["candidates"], record, out)
    except (ServiceError, ValueError) as exc:
        record.pop("article", None)
        record["decision"] = {"status": "error", "error_type": type(exc).__name__, "error": str(exc)}
        append_jsonl(failures, {"stage": "match", "step": "reapply", "entry_id": entry["entry_id"],
                                "error_type": type(exc).__name__, "error": str(exc), "at": utc_now()})
    return record


def retrieval_mode(settings: Settings) -> tuple[str, str]:
    if not settings.retrieval_base_url:
        return "lexical", "RETRIEVAL_BASE_URL is not set"
    try:
        with RetrievalClient(settings.retrieval_base_url, settings.retrieval_api_key, timeout=15) as client:
            client.verify_models()
        return "model", "retrieval models verified"
    except (ServiceError, ValueError) as exc:
        return "lexical", f"retrieval service unavailable: {exc}"


def skip_reason(entry: dict[str, Any]) -> str | None:
    """The reason the match stage does not search an entry, or None."""
    if entry["chars"] < MIN_ENTRY_CHARS:
        return f"fewer than {MIN_ENTRY_CHARS} characters"
    if not entry["headword"] and entry["chars"] < MIN_UNTITLED_CHARS:
        return "no headword and short text"
    return None


def llm_terms(settings: Settings, entry: dict[str, Any], pages: dict[str, dict[str, Any]],
              scan_dir: Path, out: Path, failures: Path) -> dict[str, Any]:
    """The Super VL title guess and terms for one entry, or a skip/failure result. Never raises."""
    if not settings.super_api_key:
        return {"status": "skipped", "reason": "SUPER_API_KEY is not set"}
    path = out / "terms" / f"{entry['entry_id']}.json"
    try:
        with ChatClient(settings.super_base_url, settings.super_api_key, settings.super_model) as client:
            record = terms_stage.suggest(client, entry, pages, scan_dir, path)
        return {"status": "ok", "model": record["model"], "title": record["parsed"].get("title"),
                "terms": record["parsed"]["terms"], "cached": record.get("cached", False),
                "raw_path": f"terms/{entry['entry_id']}.json"}
    except (ServiceError, ValueError, OSError) as exc:
        append_jsonl(failures, {"stage": "match_terms", "entry_id": entry["entry_id"],
                                "error_type": type(exc).__name__, "error": str(exc), "at": utc_now()})
        result: dict[str, Any] = {"status": "failed", "error_type": type(exc).__name__, "error": str(exc)}
        if path.is_file():
            result["raw_path"] = f"terms/{entry['entry_id']}.json"
        return result


def match_entry(settings: Settings, entry: dict[str, Any], mode: str, out: Path, failures: Path,
                pages: dict[str, dict[str, Any]] | None = None, scan_dir: Path | None = None) -> dict[str, Any]:
    """Search, score, and decide one entry. Write its candidates to out/candidates and articles to out/articles."""
    record: dict[str, Any] = {"entry_id": entry["entry_id"], "headword": entry["headword"],
                              "entry_text_sha256": entry["text_sha256"], "mode": mode}
    try:
        record["search_terms"] = {
            "frequency": keywords(keyword_source(entry, pages)),
            "dictionary_filter": bool(system_words()),
            "llm": (llm_terms(settings, entry, pages, scan_dir, out, failures)
                    if pages and scan_dir else {"status": "skipped", "reason": "no page records or scan directory"}),
        }
        with WikiClient(settings.wikipedia_api_url) as wiki:
            searches: list[dict[str, Any]] = []
            used, rows = candidates(wiki, entry, searches, pages=pages, llm=record["search_terms"]["llm"])
            record["queries"] = used
            record["searches"] = searches
            if mode == "model" and rows:
                with RetrievalClient(settings.retrieval_base_url, settings.retrieval_api_key) as retrieval:
                    record["query_chars"] = model_scores(retrieval, entry, rows)
            record["headword_variant"] = headword_variant(entry["headword"])
            record["candidate_count"] = len(rows)
            record["list_pages_removed_after_fetch"] = []
            finish_match(wiki, entry, rows, record, out)
    except (ServiceError, ValueError) as exc:
        record["decision"] = {"status": "error", "error_type": type(exc).__name__, "error": str(exc)}
        append_jsonl(failures, {"stage": "match", "entry_id": entry["entry_id"], "error_type": type(exc).__name__,
                                "error": str(exc), "at": utc_now()})
    return record


def run(settings: Settings, work_dir: Path, raw_scans: Path = Path("data/raw/britannica")) -> dict[str, Any]:
    from .storage import LanceArtifactStore

    source = text_dir(work_dir)
    entries = read_jsonl(source / "entries.jsonl")
    pages = {p["page_id"]: p for p in read_jsonl(source / "pages.jsonl")}
    out = work_dir / "match"
    mode, mode_detail = retrieval_mode(settings)
    selected, skipped = [], []
    for entry in entries:
        reason = skip_reason(entry)
        if reason:
            skipped.append({"entry_id": entry["entry_id"], "reason": reason})
        else:
            selected.append(entry)

    failures = work_dir / "runs" / "failures.jsonl"
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(
            lambda entry: match_entry(settings, entry, mode, out, failures, pages, raw_scans), selected))
    write_jsonl(out / "matches.jsonl", records)
    write_jsonl(out / "skipped.jsonl", skipped)

    manifest = load_manifest()
    manifest_pages = {p["page_id"]: p for p in manifest["pages"]}
    by_entry = {e["entry_id"]: e for e in entries}
    match_records = []
    for record in records:
        if record["decision"]["status"] != "accepted":
            continue
        article = read_json(out / "articles" / f"{record['article']['page_id']}.json")
        match_records.append(ArtifactRecord(
            record_id=f"match:{record['entry_id']}", stage="match", artifact_path=str(out / "matches.jsonl"),
            sources=[scan_reference(manifest_pages[p["page_id"]], manifest)
                     for p in by_entry[record["entry_id"]]["pages"]]
            + [wiki_reference(article)],
            metadata={"method": record["decision"]["method"], "title": article["title"]},
        ))
    provenance = LanceArtifactStore(settings.db_path, work_dir).replace_stage("match", match_records)
    accepted = [r for r in records if r["decision"]["status"] == "accepted"]
    repeats = Counter(r["article"]["page_id"] for r in accepted)
    llm_results = [r["search_terms"]["llm"] for r in records if r.get("search_terms")]
    models = [EMBED_MODEL, RERANK_MODEL] if mode == "model" else []
    if any(r["status"] == "ok" for r in llm_results):
        models = [*models, SUPER_MODEL]
    summary = {
        "stage": "match", "finished_at": utc_now(), "entry_text": source.name, "provenance": provenance, "mode": mode, "mode_detail": mode_detail,
        "models": models,
        "terms_model": SUPER_MODEL,
        "llm_terms": {"ok": sum(r["status"] == "ok" for r in llm_results),
                      "cached": sum(1 for r in llm_results if r.get("cached")),
                      "failed": sum(r["status"] == "failed" for r in llm_results),
                      "skipped": sum(r["status"] == "skipped" for r in llm_results)},
        "wikipedia_revision": WIKIPEDIA_REVISION,
        "thresholds": {"title_similarity": TITLE_ACCEPT} if mode == "lexical"
        else model_thresholds(),
        "entries": len(entries), "skipped": len(skipped), "searched": len(records), "accepted": len(accepted),
        "rejected": sum(r["decision"]["status"] == "rejected" for r in records),
        "headword_variants": {r["entry_id"]: r["headword_variant"] for r in records if r.get("headword_variant")},
        "list_pages_removed_after_fetch": sum(len(r.get("list_pages_removed_after_fetch", [])) for r in records),
        "errors": sum(r["decision"]["status"] == "error" for r in records),
        "repeated_articles": {page: count for page, count in repeats.items() if count > 1},
        "outputs": {"matches": str(out / "matches.jsonl"), "candidates": str(out / "candidates"),
                    "articles": str(out / "articles")},
    }
    write_json(out / "summary.json", summary)
    return summary
