"""Evaluate stage: check saved agent runs, write the six case studies, and record the reproduction setup.

Method (team choice):
1. The team classifies cases by hand in docs/evaluation/cases.json. Each case names a saved run.
2. For each saved run, check every quoted passage of 25 or more characters against the tool results of
   that run. An exact match after whitespace and case folding is "exact"; a close match (ratio >= 0.85) is
   "close"; anything else is "unsupported".
3. Write one case study per case from templates/case-study.md, with the run record, citations, tool calls,
   the answer, and the quote check.
4. Record the code revision, model IDs, data revisions, tool versions, and known limits.
"""
from __future__ import annotations

import difflib
import json
from pathlib import Path
import platform
import re
import subprocess
from typing import Any

from .common import read_json, read_jsonl, utc_now, write_json, write_text
from .config import (
    EMBED_MODEL, EMBED_REVISION, PARSE_MODEL, RERANK_MODEL, RERANK_REVISION, SUPER_MODEL, WIKIPEDIA_REVISION, Settings,
)
from .data import load_manifest

REPO = Path(__file__).resolve().parents[2]
QUOTE_MARK = re.compile(r"[\"“”]")


def quotes_in(answer: str) -> list[str]:
    """Quoted passages: on each line, the text between the 1st and 2nd quote mark, the 3rd and 4th, and so on."""
    found = []
    for line in answer.splitlines():
        found += [part for part in QUOTE_MARK.split(line)[1::2] if 25 <= len(part) <= 400]
    return list(dict.fromkeys(found))


def fold(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("’", "'").replace("‘", "'")).strip().lower()


def quote_support(answer: str, sources: str) -> list[dict[str, Any]]:
    """Check each quoted passage of the answer against the source text the tools returned."""
    folded = fold(sources)
    rows = []
    for quote in quotes_in(answer):
        q = fold(quote)
        # The agent may shorten a quote with "..." or add words in [brackets]. Check each remaining part.
        parts = [p.strip(" ,.;:") for p in re.split(r"\[[^\]]*\]|\.\.\.|…", q) if len(p.strip()) >= 12]
        if parts and all(p in folded for p in parts):
            rows.append({"quote": quote, "support": "exact"})
            continue
        ratios, windows = [], []
        for part in parts or [q]:
            matcher = difflib.SequenceMatcher(None, folded, part, autojunk=False)
            block = matcher.find_longest_match(0, len(folded), 0, len(part))
            start = max(0, block.a - block.b)
            window = folded[start:start + len(part) + 10]
            ratios.append(difflib.SequenceMatcher(None, window, part, autojunk=False).ratio())
            windows.append(window)
        ratio = min(ratios)
        rows.append({"quote": quote, "support": "close" if ratio >= 0.85 else "unsupported",
                     "best_ratio": round(ratio, 3), "best_window": " / ".join(windows)[:300]})
    return rows


def tool_text(events_path: Path) -> str:
    """The source text the tools returned in one run, decoded from their JSON results."""
    parts = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") != "tool_result":
            continue
        output = event.get("output", "")
        try:
            parts.append(json.dumps(json.loads(output), ensure_ascii=False))
            parts.append(_strings(json.loads(output)))
        except (ValueError, TypeError):
            parts.append(str(output))
    return "\n".join(parts)


def _strings(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_strings(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(_strings(v) for v in value)
    return str(value)


def git(*args: str) -> str:
    done = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    return done.stdout.strip()


def repaired_section(repair: dict[str, Any], run: dict[str, Any], quotes: list[dict[str, Any]]) -> str:
    """The repaired run, kept separate from the failed run that the classification describes."""
    checks = run["checks"]
    quote_lines = "\n".join(f"- {q['support']}: \"{q['quote'][:160]}\"" for q in quotes) or "- No quoted passages."
    return f"""
## Repaired run

The classification above describes the failed run. This section records a later run after a repair.

Run record: `{run['events_path']}` (run `{run['run_id']}`, question `{run['question_id']}`, Hermes session `{run['session_id']}`)
Repair outcome: {repair['outcome']}

- Tool calls, in order: {', '.join(run['tool_calls']) or 'none'}
- Britannica entry IDs cited: {', '.join(checks['cited_entry_ids']) or 'none'}
- Wikipedia revision IDs cited: {', '.join(checks['cited_revision_ids']) or 'none'}
- Cited IDs absent from tool results: {', '.join(checks['unsupported_entry_ids'] + checks['unsupported_revision_ids']) or 'none'}
- Automatic check: {'pass' if checks['auto_pass'] else 'fail'}
- Quoted passages checked against the tool results of this run:
{quote_lines}

{repair['note']}

<details><summary>Repaired agent answer</summary>

{run['answer']}

</details>
"""


def case_study(case: dict[str, Any], run: dict[str, Any], quotes: list[dict[str, Any]], revision: str,
               repaired: str = "") -> str:
    checks = run["checks"]
    quote_lines = "\n".join(f"- {q['support']}: \"{q['quote'][:160]}\"" for q in quotes) or "- No quoted passages."
    calls = ", ".join(run["tool_calls"]) or "none"
    return f"""# Case study

Case ID: {case['case_id']}
Classification: {case['classification']}
Run record: `{run['events_path']}` (run `{run['run_id']}`, question `{run['question_id']}`, Hermes session `{run['session_id']}`)
Code revision: `{revision}`

## Question

{run['question']}

## Evidence

- Model: `{run['model']}` (expected `{SUPER_MODEL}`: {checks['model_ok']})
- Tool calls, in order: {calls}
- Britannica entry IDs cited: {', '.join(checks['cited_entry_ids']) or 'none'}
- Wikipedia revision IDs cited: {', '.join(checks['cited_revision_ids']) or 'none'}
- Cited IDs absent from tool results: {', '.join(checks['unsupported_entry_ids'] + checks['unsupported_revision_ids']) or 'none'}
- Quoted passages checked against the tool results of this run:
{quote_lines}

## Result

{case['reason']}

Limits: {case['limits']}
{('Repair: ' + case['repair']) if case.get('repair') else ''}

Automatic check: {'pass' if checks['auto_pass'] else 'fail'}. The automatic check uses text rules. This classification comes from a manual review of the answer and the sources.

<details><summary>Agent answer</summary>

{run['answer']}

</details>
{repaired}"""


def run(settings: Settings, work_dir: Path) -> dict[str, Any]:
    del settings
    runs = read_jsonl(work_dir / "agent" / "runs.jsonl")
    spec = read_json(REPO / "docs" / "evaluation" / "cases.json")
    by_key = {(r["run_id"], r["question_id"]): r for r in runs}
    out = work_dir / "evaluate"
    revision = git("rev-parse", "HEAD") + (" + uncommitted changes" if git("status", "--porcelain") else "")

    checked = []
    for record in runs:
        sources = tool_text(Path(record["events_path"]))
        quotes = quote_support(record["answer"], sources)
        checked.append({"run_id": record["run_id"], "question_id": record["question_id"],
                        "auto_pass": record["checks"]["auto_pass"], "quotes": len(quotes),
                        "unsupported_quotes": [q["quote"] for q in quotes if q["support"] == "unsupported"],
                        "quote_checks": quotes})
    quotes_by_key = {(c["run_id"], c["question_id"]): c["quote_checks"] for c in checked}

    cases, missing = [], []
    for case in spec["cases"]:
        key = (case["run_id"], case["question_id"])
        if key not in by_key:
            missing.append(case["case_id"])
            continue
        repaired, repair = "", case.get("repaired_run")
        if repair:
            repair_key = (repair["run_id"], repair["question_id"])
            if repair_key not in by_key:
                missing.append(f"{case['case_id']} (repaired run)")
                continue
            repaired = repaired_section(repair, by_key[repair_key], quotes_by_key[repair_key])
        document = case_study(case, by_key[key], quotes_by_key[key], revision, repaired)
        write_text(out / "cases" / f"{case['case_id']}.md", document)
        cases.append({"case_id": case["case_id"], "classification": case["classification"],
                      "run": f"{case['run_id']}/{case['question_id']}", "auto_pass": by_key[key]["checks"]["auto_pass"],
                      "unsupported_quotes": sum(q["support"] == "unsupported" for q in quotes_by_key[key]),
                      "repaired_run": f"{repair['run_id']}/{repair['question_id']}" if repair else None,
                      "repair_outcome": repair["outcome"] if repair else None})
    if missing:
        raise ValueError(f"cases name runs that are not saved: {missing}")
    counts = {kind: sum(c["classification"] == kind for c in cases) for kind in ("success", "failure")}

    stage = {s: read_json(work_dir / s / "summary.json") for s in ("extract", "match", "compare", "agent", "site")
             if (work_dir / s / "summary.json").is_file()}
    manifest = load_manifest()
    reproduction = {
        "code_revision": revision, "python": platform.python_version(), "platform": platform.platform(),
        "models": {"parse": PARSE_MODEL, "embed": f"{EMBED_MODEL}@{EMBED_REVISION}",
                   "rerank": f"{RERANK_MODEL}@{RERANK_REVISION}", "agent": SUPER_MODEL,
                   "embed_rerank_used": stage.get("match", {}).get("mode") == "model"},
        "data": {"britannica_dataset": manifest["dataset"], "britannica_revision": manifest["revision"],
                 "manifest_sha256": manifest["manifest_sha256"], "wikipedia_revision": WIKIPEDIA_REVISION},
        "tools": {"hermes": stage.get("agent", {}).get("hermes_version"),
                  "latex": stage.get("site", {}).get("latex", {}).get("engine")},
        "commands": ["uv sync --locked", "uv run nemotron-challenge data fetch",
                     *[f"uv run nemotron-challenge run {s}" for s in ("extract", "match", "compare", "agent", "site",
                                                                       "evaluate")]],
    }
    limits = [
        "The match stage ran in lexical mode. The Nemotron embedder and reranker were not reachable, so every "
        "match is provisional_lexical and needs the model check.",
        "Scans are 600 x 874 pixels. Parse OCR has many errors; about "
        f"{stage.get('compare', {}).get('britannica_unverified_rate')} of Britannica tokens are outside the vocabulary.",
        f"Parse looped on {len(stage.get('extract', {}).get('failed_scans', []))} scans (a blank cover and an "
        "engraved plate) and hit its token limit. These scans have no extracted text.",
        "The first match run accepted list pages (\"Coinage\", \"Willin'\") that lack \"(disambiguation)\" in the "
        "title. The repaired rule removes pages that open with \"may refer to\". When the right article is not a "
        "BM25 candidate (\"Coining (mint)\"), the entry now has no match.",
        "OCR-damaged headwords get a dictionary variant only when one close word exists (PHILLOOGY -> philology). "
        "Ambiguous damage (WILLIN) and damage below the 0.85 ratio still break search and matching.",
        "The lexical rule still accepts wrong senses with the same title (\"Naxos (Crete)\" for the Aegean island).",
        "Automatic agent checks pass answers with unsupported metadata or wrong inferences. Manual review is needed.",
    ]
    report = {"stage": "evaluate", "finished_at": utc_now(), "cases": cases, "counts": counts,
              "runs_checked": len(checked), "runs_with_unsupported_quotes": [
                  f"{c['run_id']}/{c['question_id']}" for c in checked if c["unsupported_quotes"]],
              "quote_check_review": spec.get("quote_check_review", []),
              "observations_after_repair": spec.get("observations_after_repair", []),
              "reproduction": reproduction, "known_limits": limits,
              "outputs": {"cases": str(out / "cases"), "quote_checks": str(out / "quote_checks.json")}}
    write_json(out / "quote_checks.json", checked)
    write_json(out / "summary.json", report)
    return report
