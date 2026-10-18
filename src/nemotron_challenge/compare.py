"""Compare stage: vocabulary and word frequencies of matched Britannica entries and Wikipedia articles.

Method (team choice):
1. Tokenise both texts: lower case, letters only, at least 3 letters, without stop words.
2. Normalise Britannica text and tokens and log each change:
   - abbreviations: printed abbreviations such as "Brit." expand before counting ("Brit." -> "British").
     Source snippets keep the printed form.
   - long s: old print uses a long s that OCR reads as "f" ("perfons"). Replace "f" with "s" when the
     result is in the reference vocabulary and the original is not.
   - historical spelling: a short fixed table ("connexion" -> "connection").
3. The reference vocabulary is the set of words in all cached Wikipedia articles, plus the system word
   list (/usr/share/dict/words) when it exists. The summary records its checksum. A Britannica token
   outside the vocabulary is "unverified" (an OCR error or a rare word). Count it, but exclude it from
   term lists. Plurals and inflections outside the word list also count as unverified.
4. For each pair: token and type counts, Jaccard overlap of the 100 most frequent terms per side
   (this limits the length effect), cosine of relative frequencies, shared terms, and distinctive terms
   by log-odds with an informative Dirichlet prior (Monroe, Colaresi and Quinn 2008).
5. For the corpus: the same log-odds over all matched entries against all distinct matched articles.
   Each distinctive term carries one source snippet per side as evidence.
"""
from __future__ import annotations

from collections import Counter
import html
import math
from pathlib import Path
import re
from typing import Any

from .common import (
    WORD_LIST, read_json, read_jsonl, sha256_bytes, sha256_text, text_dir, utc_now, write_json, write_jsonl, write_text,
)
from .config import Settings
from .match import STOPWORDS

TOP_TERMS = 100
DISTINCTIVE = 15
MIN_COUNT = 2
HISTORICAL = {
    "connexion": "connection", "shew": "show", "shewn": "shown", "shews": "shows", "compleat": "complete",
    "publick": "public", "musick": "music", "physick": "physic", "logick": "logic", "ancle": "ankle",
    "chymistry": "chemistry", "chymical": "chemical", "phrenzy": "frenzy", "gaol": "jail", "antient": "ancient",
    "intire": "entire", "inclose": "enclose", "croud": "crowd", "authour": "author", "errour": "error",
    "terrour": "terror", "emperour": "emperor", "governour": "governor", "aera": "era", "oeconomy": "economy",
}




def reference_vocabulary(articles: dict[str, dict[str, Any]]) -> tuple[set[str], list[dict[str, Any]]]:
    """Words of the cached Wikipedia articles, plus the system word list when it exists."""
    vocabulary = {w for a in articles.values() for w in tokens(a["text"])}
    sources = [{"source": "cached Wikipedia articles", "documents": len(articles), "words": len(vocabulary)}]
    if WORD_LIST.is_file():
        data = WORD_LIST.read_bytes()
        listed = {w.lower() for w in data.decode("utf-8", "ignore").split()}
        vocabulary |= listed
        sources.append({"source": str(WORD_LIST), "sha256": sha256_bytes(data), "words": len(listed)})
    return vocabulary, sources


# Printed abbreviation -> full word. OCR can read the full stop as another punctuation mark ("Brit;").
ABBREVIATIONS = {"Brit.": "British"}


def expand_abbreviations(text: str, log: Counter) -> str:
    for short, full in ABBREVIATIONS.items():
        text, count = re.subn(rf"\b{re.escape(short[:-1])}(?=[.;:,])", full, text)
        if count:
            log[("abbreviation", short, full)] += count
    return text


def britannica_tokens(text: str, log: Counter) -> list[str]:
    return tokens(expand_abbreviations(text, log))


def tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 3 and w not in STOPWORDS]


def long_s_variants(word: str) -> list[str]:
    """Each way to read one or more "f" letters as "s", in a bounded number."""
    positions = [i for i, char in enumerate(word) if char == "f"][:4]
    variants = []
    for mask in range(1, 2 ** len(positions)):
        chars = list(word)
        for bit, position in enumerate(positions):
            if mask >> bit & 1:
                chars[position] = "s"
        variants.append("".join(chars))
    return variants


def normalise(words: list[str], vocabulary: set[str], log: Counter) -> tuple[list[str], Counter]:
    result, unverified = [], Counter()
    for word in words:
        if word in HISTORICAL:
            log[("historical", word, HISTORICAL[word])] += 1
            word = HISTORICAL[word]
        elif word not in vocabulary and "f" in word:
            fixed = next((v for v in long_s_variants(word) if v in vocabulary), None)
            if fixed:
                log[("long_s", word, fixed)] += 1
                word = fixed
        if word not in vocabulary:
            unverified[word] += 1
            continue
        result.append(word)
    return result, unverified


def log_odds(a: Counter, b: Counter, prior: Counter) -> dict[str, float]:
    """z-scores of the log-odds ratio of each word in a against b, with an informative Dirichlet prior."""
    n_a, n_b, a0 = sum(a.values()), sum(b.values()), sum(prior.values())
    scores = {}
    for word in set(a) | set(b):
        if a[word] + b[word] < MIN_COUNT:
            continue
        alpha = prior[word] or 0.01
        la = math.log((a[word] + alpha) / (n_a + a0 - a[word] - alpha))
        lb = math.log((b[word] + alpha) / (n_b + a0 - b[word] - alpha))
        variance = 1 / (a[word] + alpha) + 1 / (b[word] + alpha)
        scores[word] = (la - lb) / math.sqrt(variance)
    return scores


def snippet(text: str, word: str, width: int = 90) -> dict[str, Any] | None:
    match = re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE)
    if not match:
        return None
    start, end = max(0, match.start() - width), min(len(text), match.end() + width)
    return {"offset": match.start(), "text": re.sub(r"\s+", " ", text[start:end]).strip()}


def cosine(a: Counter, b: Counter) -> float:
    dot = sum(a[w] * b[w] for w in set(a) & set(b))
    norm = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return round(dot / norm, 4) if norm else 0.0


def term_rows(scores: dict[str, float], count_b: Counter, count_w: Counter,
              texts: tuple[str, str]) -> list[dict[str, Any]]:
    """The highest-scoring terms, with counts and one source snippet per side."""
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:DISTINCTIVE]
    return [{"term": word, "z": round(z, 3), "count_britannica": count_b[word], "count_wikipedia": count_w[word],
             "britannica_snippet": snippet(texts[0], word), "wikipedia_snippet": snippet(texts[1], word)}
            for word, z in ranked]


def compare_pair(entry: dict[str, Any], article: dict[str, Any], vocabulary: set[str],
                 prior: Counter, log: Counter) -> dict[str, Any]:
    raw_b = britannica_tokens(entry["text"], log)
    words_b, unverified = normalise(raw_b, vocabulary, log)
    words_w = tokens(article["text"])
    count_b, count_w = Counter(words_b), Counter(words_w)
    top_b = {w for w, _ in count_b.most_common(TOP_TERMS)}
    top_w = {w for w, _ in count_w.most_common(TOP_TERMS)}
    scores = log_odds(count_b, count_w, prior)
    texts = (entry["text"], article["text"])
    shared = sorted(set(count_b) & set(count_w), key=lambda w: -(count_b[w] / len(words_b) + count_w[w] / len(words_w)))
    return {
        "britannica": {"tokens_raw": len(raw_b), "tokens_kept": len(words_b), "types": len(count_b),
                       "unverified_tokens": sum(unverified.values()),
                       "unverified_rate": round(sum(unverified.values()) / len(raw_b), 4) if raw_b else None,
                       "unverified_examples": [w for w, _ in unverified.most_common(10)]},
        "wikipedia": {"tokens": len(words_w), "types": len(count_w)},
        "length_ratio_wiki_to_britannica": round(len(words_w) / len(words_b), 3) if words_b else None,
        "top_terms_jaccard": round(len(top_b & top_w) / len(top_b | top_w), 4) if top_b | top_w else 0.0,
        "frequency_cosine": cosine(count_b, count_w),
        "shared_terms": [{"term": w, "count_britannica": count_b[w], "count_wikipedia": count_w[w]} for w in shared[:20]],
        "distinctive_britannica": term_rows(scores, count_b, count_w, texts),
        "distinctive_wikipedia": term_rows({w: -z for w, z in scores.items()}, count_b, count_w, texts),
    }


def bar_chart(path: Path, title: str, rows: list[tuple[str, float]], colour: str) -> None:
    """Write a horizontal bar chart as SVG with no plotting dependency."""
    width, bar, left, top = 640, 18, 150, 50
    height = top + bar * len(rows) + 30
    peak = max((abs(v) for _, v in rows), default=1) or 1
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="sans-serif" '
             f'font-size="12"><rect width="100%" height="100%" fill="white"/>',
             f'<text x="10" y="22" font-size="14" font-weight="bold">{html.escape(title)}</text>',
             f'<text x="10" y="40" fill="#555">log-odds z-score (informative Dirichlet prior)</text>']
    for i, (label, value) in enumerate(rows):
        y = top + i * bar
        length = (width - left - 60) * abs(value) / peak
        parts.append(f'<text x="{left - 6}" y="{y + 13}" text-anchor="end">{html.escape(label)}</text>')
        parts.append(f'<rect x="{left}" y="{y + 3}" width="{length:.1f}" height="{bar - 6}" fill="{colour}"/>')
        parts.append(f'<text x="{left + length + 4:.1f}" y="{y + 13}" fill="#333">{value:.1f}</text>')
    parts.append("</svg>")
    write_text(path, "\n".join(parts) + "\n")


def compare_matches(entries: dict[str, dict[str, Any]], matches: list[dict[str, Any]],
                    articles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compare each accepted match. The prior and the reference vocabulary come from these pairs only."""
    vocabulary, vocabulary_sources = reference_vocabulary(articles)
    prior = Counter(w for a in articles.values() for w in tokens(a["text"]))
    for entry_id in {m["entry_id"] for m in matches}:
        prior.update(britannica_tokens(entries[entry_id]["text"], Counter()))
    log: Counter = Counter()
    pairs = []
    for match in matches:
        entry, article = entries[match["entry_id"]], articles[match["article"]["page_id"]]
        if article["text_sha256"] != sha256_text(article["text"]):
            raise ValueError(f"cached article {article['page_id']} text differs from its checksum")
        result = compare_pair(entry, article, vocabulary, prior, log)
        pairs.append({
            "entry_id": entry["entry_id"], "headword": entry["headword"], "entry_text_sha256": entry["text_sha256"],
            "scan_pages": [p["page_id"] for p in entry["pages"]], "match_method": match["decision"]["method"],
            "article": {k: article[k] for k in ("page_id", "revision_id", "title", "url", "revision_url", "text_sha256")},
            **result,
        })
    return {"pairs": pairs, "vocabulary": vocabulary, "vocabulary_sources": vocabulary_sources, "prior": prior,
            "log": log}


def run(settings: Settings, work_dir: Path) -> dict[str, Any]:
    del settings
    source = text_dir(work_dir)
    entries = {e["entry_id"]: e for e in read_jsonl(source / "entries.jsonl")}
    matches = [m for m in read_jsonl(work_dir / "match" / "matches.jsonl") if m["decision"]["status"] == "accepted"]
    if not matches:
        raise ValueError("The match stage accepted no pairs. Nothing to compare.")
    articles = {pid: read_json(work_dir / "match" / "articles" / f"{pid}.json")
                for pid in {m["article"]["page_id"] for m in matches}}
    compared = compare_matches(entries, matches, articles)
    pairs, vocabulary, vocabulary_sources = compared["pairs"], compared["vocabulary"], compared["vocabulary_sources"]
    prior, log = compared["prior"], compared["log"]
    out = work_dir / "compare"
    write_jsonl(out / "pairs.jsonl", pairs)

    # Corpus level. Count each matched entry once and each distinct article once.
    used_entries = sorted({m["entry_id"] for m in matches})
    corpus_b: Counter = Counter()
    corpus_unverified = corpus_raw = 0
    for entry_id in used_entries:
        raw = britannica_tokens(entries[entry_id]["text"], Counter())
        kept, unverified = normalise(raw, vocabulary, Counter())
        corpus_b.update(kept)
        corpus_raw += len(raw)
        corpus_unverified += sum(unverified.values())
    corpus_w = Counter(w for a in articles.values() for w in tokens(a["text"]))
    scores = log_odds(corpus_b, corpus_w, prior)
    joined_b = "\n\n".join(entries[e]["text"] for e in used_entries)
    joined_w = "\n\n".join(a["text"] for a in articles.values())
    top_b = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:25]
    top_w = sorted(scores.items(), key=lambda kv: kv[1])[:25]
    corpus = {
        "britannica_documents": len(used_entries), "wikipedia_documents": len(articles),
        "britannica_tokens_raw": corpus_raw, "britannica_tokens_kept": sum(corpus_b.values()),
        "britannica_unverified_rate": round(corpus_unverified / corpus_raw, 4) if corpus_raw else None,
        "wikipedia_tokens": sum(corpus_w.values()), "frequency_cosine": cosine(corpus_b, corpus_w),
        "distinctive_britannica": [{"term": w, "z": round(z, 3), "count_britannica": corpus_b[w],
                                    "count_wikipedia": corpus_w[w], "britannica_snippet": snippet(joined_b, w)}
                                   for w, z in top_b],
        "distinctive_wikipedia": [{"term": w, "z": round(-z, 3), "count_britannica": corpus_b[w],
                                   "count_wikipedia": corpus_w[w], "wikipedia_snippet": snippet(joined_w, w)}
                                  for w, z in top_w],
    }
    write_json(out / "corpus.json", corpus)
    write_jsonl(out / "normalisation_log.jsonl", (
        {"kind": kind, "from": src, "to": dst, "count": n} for (kind, src, dst), n in log.most_common()))
    bar_chart(out / "plots" / "distinctive-britannica.svg",
              f"Terms more frequent in Britannica ({len(used_entries)} entries vs {len(articles)} articles)",
              [(r["term"], r["z"]) for r in corpus["distinctive_britannica"][:20]], "#8a5a2b")
    bar_chart(out / "plots" / "distinctive-wikipedia.svg",
              f"Terms more frequent in Wikipedia ({len(articles)} articles vs {len(used_entries)} entries)",
              [(r["term"], r["z"]) for r in corpus["distinctive_wikipedia"][:20]], "#2b5a8a")
    summary = {
        "stage": "compare", "finished_at": utc_now(), "entry_text": source.name, "method": "word frequencies, log-odds with Dirichlet prior",
        "pairs": len(pairs), "britannica_documents": len(used_entries), "wikipedia_documents": len(articles),
        "match_methods": dict(Counter(p["match_method"] for p in pairs)),
        "normalisation_changes": {kind: sum(n for (k, _, _), n in log.items() if k == kind)
                                  for kind in ("abbreviation", "long_s", "historical")},
        "britannica_unverified_rate": corpus["britannica_unverified_rate"], "vocabulary_sources": vocabulary_sources,
        "mean_top_terms_jaccard": round(sum(p["top_terms_jaccard"] for p in pairs) / len(pairs), 4),
        "mean_frequency_cosine": round(sum(p["frequency_cosine"] for p in pairs) / len(pairs), 4),
        "outputs": {"pairs": str(out / "pairs.jsonl"), "corpus": str(out / "corpus.json"),
                    "normalisation_log": str(out / "normalisation_log.jsonl"), "plots": str(out / "plots")},
    }
    write_json(out / "summary.json", summary)
    return summary
