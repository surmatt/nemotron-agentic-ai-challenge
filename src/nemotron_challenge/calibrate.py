"""Calibrate the model match rule on hand-labelled entries, and compare it with simpler rankers.

Method (team choice):
- Labels: docs/evaluation/match_labels.json (60 entries, half for calibration, half for test).
- Rule: take the candidate that the reranker ranks first. Accept it when its raw logit >= L, its
  margin to the next candidate >= M, its embedder cosine >= C, and its title similarity to the
  headword >= T. T = 0 turns the title test off. The grid includes the first GPU-run rule
  (L = -6.0, T = 0.75, no margin, no cosine) from main.
- Out-of-sample estimate: two-fold cross-validation. Fit (L, M, C) on one half, apply it to the other
  half, and pool the two held-out halves.
- Final thresholds: the best F1 on all labelled entries. Their in-sample score is optimistic; report the
  cross-validated score.
- A true positive is an accepted candidate in the entry's accept list. Recall counts entries with a
  non-empty accept list.
"""
from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import Any, Callable

from .common import read_json, utc_now, write_json
from . import match

LOGITS = [x / 2 for x in range(-20, 7)]
MARGINS = [x / 4 for x in range(0, 13)]
COSINES = [x / 20 for x in range(0, 9)]
TITLES = [0.0, 0.5, 0.75, 0.85]
THRESHOLDS = Path("docs/evaluation/match_thresholds.json")


def score(choices: dict[str, str | None], labels: dict[str, list[str]]) -> dict[str, Any]:
    """Precision, recall, and F1 of accepted choices (entry -> page_id or None) against accept lists."""
    accepted = {e: p for e, p in choices.items() if p is not None}
    tp = sum(p in labels[e] for e, p in accepted.items())
    fp = len(accepted) - tp
    positives = sum(bool(v) for v in labels.values())
    precision = tp / len(accepted) if accepted else 0.0
    recall = tp / positives if positives else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"accepted": len(accepted), "true_positive": tp, "false_positive": fp, "positives": positives,
            "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


def top(rows: list[dict[str, Any]], key: Callable[[dict[str, Any]], Any]) -> dict[str, Any] | None:
    return max(rows, key=key) if rows else None


def model_choice(rows: list[dict[str, Any]], logit: float, margin: float, cosine: float,
                 title: float = 0.0) -> str | None:
    if not rows:
        return None
    ranked = sorted(rows, key=lambda r: r["rerank_position"])
    best = ranked[0]
    gap = best["rerank_logit"] - ranked[1]["rerank_logit"] if len(ranked) > 1 else float("inf")
    ok = (best["rerank_logit"] >= logit and gap >= margin and best["cosine"] >= cosine
          and best["title_similarity"] >= title)
    return best["page_id"] if ok else None


def run(work_dir: Path) -> dict[str, Any]:
    spec = read_json(Path("docs/evaluation/match_labels.json"))
    labels = {e["entry_id"]: e["accept"] for e in spec["entries"]}
    split = {e["entry_id"]: e["split"] for e in spec["entries"]}
    rows = {e: read_json(work_dir / "match" / "candidates" / f"{e}.json")["candidates"] for e in labels}
    if any("rerank_logit" not in r for rs in rows.values() for r in rs):
        raise ValueError("candidates have no model scores. Run match with the retrieval service first.")

    def part(name: str) -> dict[str, list[str]]:
        return {e: v for e, v in labels.items() if split[e] == name}

    cal, test = part("calibrate"), part("test")

    def fit(part_labels: dict[str, list[str]]) -> tuple[float, float, float]:
        def key(params):
            result = score({e: model_choice(rows[e], *params) for e in part_labels}, part_labels)
            return result["f1"], result["precision"], -params[0], -params[1]
        return max(product(LOGITS, MARGINS, COSINES, TITLES), key=key)

    held_out, folds = {}, []
    for train, held in ((cal, test), (test, cal)):
        params = fit(train)
        folds.append(params)
        held_out.update({e: model_choice(rows[e], *params) for e in held})
    logit, margin, cosine, title = fit(labels)

    def always(choose: Callable[[list[dict[str, Any]]], dict[str, Any] | None], part_labels):
        return score({e: (c["page_id"] if (c := choose(rows[e])) else None) for e in part_labels}, part_labels)

    def lexical(part_labels):
        out = {}
        for e in part_labels:
            decision = match.decide({}, rows[e], "lexical")
            out[e] = decision["page_id"] if decision["status"] == "accepted" else None
        return score(out, part_labels)

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
            "model_rule_calibrated": score({e: model_choice(rows[e], logit, margin, cosine, title)
                                            for e in labels_part}, labels_part),
            "first_gpu_run_rule": score({e: model_choice(rows[e], -6.0, 0.0, -1.0, 0.75) for e in labels_part},
                                        labels_part),
        }
    cross_validated = score(held_out, labels)
    thresholds = {"rerank_logit": logit, "margin": margin, "cosine": cosine, "title_similarity": title,
                  "calibrated_at": utc_now(), "labels": "docs/evaluation/match_labels.json",
                  "fit_on": "all labelled entries", "in_sample": comparison["all"]["model_rule_calibrated"],
                  "two_fold_cross_validated": cross_validated, "fold_params": folds}
    write_json(THRESHOLDS, thresholds)
    report = {"stage": "calibrate", "finished_at": utc_now(), "thresholds": thresholds, "comparison": comparison,
              "lexical_rule_all": comparison["all"]["lexical_title_rule"], "labels": len(labels), "calibration_entries": len(cal), "test_entries": len(test)}
    write_json(work_dir / "match" / "calibration.json", report)
    return report
