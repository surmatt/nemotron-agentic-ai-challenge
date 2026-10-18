"""Calibrate the model match rule on hand-labelled entries, and compare it with simpler rankers.

Method (team choice):
- Labels: docs/evaluation/match_labels.json (60 entries, half for calibration, half for test).
- Rule: take the candidate that the reranker ranks first. Accept it when its raw logit >= L, its
  embedder cosine >= C, and its title similarity to the headword >= T. The score gap to the runner-up
  does not affect acceptance. T = 0 turns the title test off. The grid includes the first GPU-run rule
  (L = -6.0, T = 0.75, no margin, no cosine) from main.
- Out-of-sample estimate: two-fold cross-validation. Fit (L, C, T) on one half, apply it to the other
  half, and pool the two held-out halves.
- Final thresholds: the best F2 on all labelled entries, so recall weighs twice precision. Their
  in-sample score is optimistic; report the cross-validated score.
- A true positive is an accepted candidate in the entry's accept list. Recall counts entries with a
  non-empty accept list. When docs/evaluation/match_judged.json exists (snapshot_judged took it
  before the queries changed), an accepted page that the labeller never saw counts as "unjudged",
  not as a false positive.
"""
from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import Any, Callable

from .common import read_json, sha256_bytes, utc_now, write_json
from . import match

LOGITS = [x / 2 for x in range(-20, 7)]
COSINES = [x / 20 for x in range(0, 9)]
TITLES = [0.0, 0.5, 0.75, 0.85]
LABELS = Path("docs/evaluation/match_labels.json")
THRESHOLDS = Path("docs/evaluation/match_thresholds.json")
JUDGED = Path("docs/evaluation/match_judged.json")


def snapshot_judged(work_dir: Path, force: bool = False) -> dict[str, Any]:
    """Store the candidate page IDs the labeller saw, per labelled entry. Refuses to overwrite."""
    if JUDGED.is_file() and not force:
        raise ValueError(f"{JUDGED} exists. Pass force=True to replace it.")
    labels = read_json(LABELS)
    judged = {}
    for entry in labels["entries"]:
        path = work_dir / "match" / "candidates" / f"{entry['entry_id']}.json"
        judged[entry["entry_id"]] = {"pages": [r["page_id"] for r in read_json(path)["candidates"]],
                                     "candidates_sha256": sha256_bytes(path.read_bytes()),
                                     "source": str(path), "at": utc_now()}
    write_json(JUDGED, judged)
    return judged


def score(choices: dict[str, str | None], labels: dict[str, list[str]],
          judged: dict[str, Any] | None = None) -> dict[str, Any]:
    """Precision, recall, F1, and F2 of accepted choices (entry -> page_id or None) against accept lists.

    With `judged`, an accepted page outside the judged candidate set counts as unjudged, not wrong."""
    accepted = {e: p for e, p in choices.items() if p is not None}
    tp = sum(p in labels[e] for e, p in accepted.items())
    unjudged = sum(1 for e, p in accepted.items()
                   if p not in labels[e] and judged is not None
                   and p not in judged.get(e, {}).get("pages", ()))
    fp = len(accepted) - tp - unjudged
    positives = sum(bool(v) for v in labels.values())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / positives if positives else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    f2 = 5 * precision * recall / (4 * precision + recall) if precision + recall else 0.0
    return {"accepted": len(accepted), "true_positive": tp, "false_positive": fp, "unjudged": unjudged,
            "positives": positives,
            "precision": round(precision, 3), "recall": round(recall, 3),
            "f1": round(f1, 3), "f2": round(f2, 3)}


def top(rows: list[dict[str, Any]], key: Callable[[dict[str, Any]], Any]) -> dict[str, Any] | None:
    return max(rows, key=key) if rows else None


def model_choice(rows: list[dict[str, Any]], logit: float, cosine: float,
                 title: float = 0.0) -> str | None:
    if not rows:
        return None
    best = min(rows, key=lambda r: r["rerank_position"])
    ok = (best["rerank_logit"] >= logit and best["cosine"] >= cosine
          and best["title_similarity"] >= title)
    return best["page_id"] if ok else None


def run(work_dir: Path) -> dict[str, Any]:
    spec = read_json(LABELS)
    labels = {e["entry_id"]: e["accept"] for e in spec["entries"]}
    split = {e["entry_id"]: e["split"] for e in spec["entries"]}
    rows = {e: read_json(work_dir / "match" / "candidates" / f"{e}.json")["candidates"] for e in labels}
    if any("rerank_logit" not in r for rs in rows.values() for r in rs):
        raise ValueError("candidates have no model scores. Run match with the retrieval service first.")
    judged = read_json(JUDGED) if JUDGED.is_file() else None

    def part(name: str) -> dict[str, list[str]]:
        return {e: v for e, v in labels.items() if split[e] == name}

    cal, test = part("calibrate"), part("test")

    def fit(part_labels: dict[str, list[str]]) -> tuple[float, float, float]:
        def key(params):
            result = score({e: model_choice(rows[e], *params) for e in part_labels}, part_labels, judged)
            return result["f2"], result["precision"], -params[0], -params[1], -params[2]
        return max(product(LOGITS, COSINES, TITLES), key=key)

    held_out, folds = {}, []
    for train, held in ((cal, test), (test, cal)):
        params = fit(train)
        folds.append(params)
        held_out.update({e: model_choice(rows[e], *params) for e in held})
    logit, cosine, title = fit(labels)

    def always(choose: Callable[[list[dict[str, Any]]], dict[str, Any] | None], part_labels):
        return score({e: (c["page_id"] if (c := choose(rows[e])) else None) for e in part_labels},
                     part_labels, judged)

    def lexical(part_labels):
        out = {}
        for e in part_labels:
            decision = match.decide({}, rows[e], "lexical")
            out[e] = decision["page_id"] if decision["status"] == "accepted" else None
        return score(out, part_labels, judged)

    rankers = {
        "bm25_top1_always": lambda r: top(r, lambda x: -x["best_rank"]),
        "embedder_top1_always": lambda r: top(r, lambda x: x["cosine"]),
        "reranker_top1_always": lambda r: top(r, lambda x: -x["rerank_position"]),
    }
    comparison = {}
    for name, labels_part in (("calibrate", cal), ("test", test), ("all", labels)):
        comparison[name] = {
            **{k: always(f, labels_part) for k, f in rankers.items()},
            "lexical_title_rule": lexical(labels_part),
            "model_rule_calibrated": score({e: model_choice(rows[e], logit, cosine, title)
                                            for e in labels_part}, labels_part, judged),
            "first_gpu_run_rule": score({e: model_choice(rows[e], -6.0, -1.0, 0.75) for e in labels_part},
                                        labels_part, judged),
        }
    cross_validated = score(held_out, labels, judged)
    final_choices = {e: model_choice(rows[e], logit, cosine, title) for e in labels}
    unjudged_accepts = [
        {"entry_id": e, "page_id": p,
         "title": next((r["title"] for r in rows[e] if r["page_id"] == p), None)}
        for e, p in final_choices.items() if p is not None and p not in labels[e]
        and judged is not None and p not in judged.get(e, {}).get("pages", ())]
    labelled_pages = [(e, p) for e in labels for p in labels[e]]
    candidate_ids = {e: {r["page_id"] for r in rs} for e, rs in rows.items()}
    label_coverage = {
        "labelled_accept_pages": len(labelled_pages),
        "in_candidates": sum(p in candidate_ids[e] for e, p in labelled_pages),
        "share": round(sum(p in candidate_ids[e] for e, p in labelled_pages) / len(labelled_pages), 3)
        if labelled_pages else None,
        "new_candidates_per_entry": {e: len(candidate_ids[e] - set(judged.get(e, {}).get("pages", ())))
                                     for e in labels} if judged else None,
    }
    thresholds = {"rerank_logit": logit, "cosine": cosine, "title_similarity": title,
                  "objective": "F2", "calibrated_at": utc_now(), "labels": str(LABELS),
                  "judged_snapshot": str(JUDGED) if judged else None,
                  "fit_on": "all labelled entries", "in_sample": comparison["all"]["model_rule_calibrated"],
                  "two_fold_cross_validated": cross_validated, "fold_params": folds,
                  "unjudged_accepts": unjudged_accepts, "label_coverage": label_coverage}
    write_json(THRESHOLDS, thresholds)
    report = {"stage": "calibrate", "finished_at": utc_now(), "thresholds": thresholds, "comparison": comparison,
              "lexical_rule_all": comparison["all"]["lexical_title_rule"], "labels": len(labels),
              "calibration_entries": len(cal), "test_entries": len(test),
              "judged_snapshot": str(JUDGED) if judged else None,
              "note": None if judged else
              "no judged snapshot: every accepted page outside an accept list counts as a false positive"}
    write_json(work_dir / "match" / "calibration.json", report)
    return report
