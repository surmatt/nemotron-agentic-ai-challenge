"""Fixture tests for the match calibration rules. They prove the scoring, not match quality."""
import json

import pytest

from nemotron_challenge import calibrate, match


def cand(page_id, position, logit, cosine, title="T", sim=0.0, rank=1):
    return {"page_id": page_id, "title": title, "rerank_position": position, "rerank_logit": logit, "cosine": cosine,
            "title_similarity": sim, "best_rank": rank, "context_overlap": 0.0}


def test_score_counts_wrong_accepts_as_false_positives():
    labels = {"E1": ["1"], "E2": ["2"], "E3": []}
    result = calibrate.score({"E1": "1", "E2": "9", "E3": "5"}, labels)
    assert (result["true_positive"], result["false_positive"], result["positives"]) == (1, 2, 2)
    assert result["precision"] == 0.333 and result["recall"] == 0.5


def test_score_counts_unjudged_accepts_apart_from_false_positives():
    labels = {"E1": ["1"], "E2": ["2"]}
    judged = {"E1": {"pages": ["1", "7"]}, "E2": {"pages": ["2", "8"]}}
    result = calibrate.score({"E1": "9", "E2": "8"}, labels, judged)
    assert (result["true_positive"], result["false_positive"], result["unjudged"]) == (0, 1, 1)
    assert result["precision"] == 0.0 and result["f2"] == 0.0
    result = calibrate.score({"E1": "1", "E2": "8"}, labels, judged)
    assert (result["true_positive"], result["false_positive"]) == (1, 1)
    assert result["f2"] == round(5 * 0.5 * 0.5 / (4 * 0.5 + 0.5), 3)


def test_snapshot_judged_writes_the_seen_pages_and_refuses_to_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(calibrate, "LABELS", tmp_path / "labels.json")
    monkeypatch.setattr(calibrate, "JUDGED", tmp_path / "judged.json")
    (tmp_path / "labels.json").write_text(json.dumps(
        {"entries": [{"entry_id": "E1", "accept": ["1"], "split": "calibrate"}]}))
    path = tmp_path / "match" / "candidates" / "E1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"entry_id": "E1", "candidates": [{"page_id": "1"}, {"page_id": "2"}]}))
    judged = calibrate.snapshot_judged(tmp_path)
    assert judged["E1"]["pages"] == ["1", "2"] and len(judged["E1"]["candidates_sha256"]) == 64
    assert judged["E1"]["source"] == str(path)
    with pytest.raises(ValueError):
        calibrate.snapshot_judged(tmp_path)
    assert calibrate.snapshot_judged(tmp_path, force=True)["E1"]["pages"] == ["1", "2"]


def test_model_choice_accepts_ties_and_single_candidates():
    rows = [cand("2", 2, 1.0, 0.3), cand("1", 1, 1.0, 0.4)]
    assert calibrate.model_choice(rows, 0.0, 0.2) == "1"
    assert calibrate.model_choice([cand("1", 1, -3.0, 0.4)], -5.0, 0.0) == "1"
    assert calibrate.model_choice([], -5.0, 0.0) is None


@pytest.mark.parametrize("logit,cosine,title,accepted", [
    (-3.0, 0.2, 0.7, True),
    (-2.0, 0.3, 0.8, True),
    (-1.0, 0.2, 0.7, False),
    (-3.0, 0.4, 0.7, False),
    (-3.0, 0.2, 0.9, False),
])
def test_model_rules_check_only_the_top_candidates_absolute_scores(
        tmp_path, monkeypatch, logit, cosine, title, accepted):
    thresholds = {"rerank_logit": logit, "cosine": cosine, "title_similarity": title}
    path = tmp_path / "thresholds.json"
    path.write_text(json.dumps(thresholds))
    monkeypatch.setattr(match, "THRESHOLD_FILE", path)
    rows = [cand("2", 2, -2.1, 0.9, sim=1.0), cand("1", 1, -2.0, 0.3, sim=0.8)]
    assert calibrate.model_choice(rows, logit, cosine, title) == ("1" if accepted else None)
    decision = match.decide({}, rows, "model")
    assert decision["status"] == ("accepted" if accepted else "rejected")
    assert decision["page_id"] == "1" and decision["thresholds"] == thresholds
    assert "margin" not in decision.get("reason", "")


@pytest.mark.parametrize("gap", [0.0, 0.15, 0.4, 1.0])
def test_match_ignores_legacy_margin_thresholds(tmp_path, monkeypatch, gap):
    path = tmp_path / "match_thresholds.json"
    path.write_text(json.dumps({"rerank_logit": -10.0, "margin": 0.5, "cosine": 0.15, "title_similarity": 0.0}))
    monkeypatch.setattr(match, "THRESHOLD_FILE", path)
    rows = [cand("1", 1, -2.0, 0.3, "Heat", 1.0), cand("2", 2, -2.0 - gap, 0.2)]
    decision = match.decide({}, rows, "model")
    assert decision["status"] == "accepted" and decision["page_id"] == "1"
    assert "margin" not in decision["thresholds"]
    assert decision["margin_to_next"] == gap
    monkeypatch.setattr(match, "THRESHOLD_FILE", tmp_path / "missing.json")
    assert match.model_thresholds() == {"rerank_logit": match.RERANK_ACCEPT, "cosine": match.COSINE_ACCEPT,
                                        "title_similarity": match.MODEL_TITLE_ACCEPT}


def test_calibration_fits_and_writes_only_absolute_thresholds(tmp_path, monkeypatch):
    monkeypatch.setattr(calibrate, "LABELS", tmp_path / "labels.json")
    monkeypatch.setattr(calibrate, "JUDGED", tmp_path / "judged.json")
    monkeypatch.setattr(calibrate, "THRESHOLDS", tmp_path / "thresholds.json")
    monkeypatch.setattr(calibrate, "LOGITS", [0.0])
    monkeypatch.setattr(calibrate, "COSINES", [0.2])
    monkeypatch.setattr(calibrate, "TITLES", [0.0])
    calibrate.LABELS.write_text(json.dumps({"entries": [
        {"entry_id": "E1", "accept": ["1"], "split": "calibrate"},
        {"entry_id": "E2", "accept": ["1"], "split": "test"},
    ]}))
    folder = tmp_path / "match" / "candidates"
    folder.mkdir(parents=True)
    for entry_id in ("E1", "E2"):
        (folder / f"{entry_id}.json").write_text(json.dumps(
            {"candidates": [cand("1", 1, 1.0, 0.4), cand("2", 2, 1.0, 0.3)]}))

    report = calibrate.run(tmp_path)
    thresholds = json.loads(calibrate.THRESHOLDS.read_text())
    saved = json.loads((tmp_path / "match" / "calibration.json").read_text())
    assert thresholds == saved["thresholds"] and "margin" not in thresholds
    assert report["thresholds"]["fold_params"] == [(0.0, 0.2, 0.0), (0.0, 0.2, 0.0)]
    assert thresholds["fold_params"] == [[0.0, 0.2, 0.0], [0.0, 0.2, 0.0]]
    assert thresholds["two_fold_cross_validated"]["true_positive"] == 2
    assert thresholds["in_sample"]["accepted"] == 2 and thresholds["objective"] == "F2"


def test_rejection_reports_only_the_failed_condition_at_full_precision(monkeypatch):
    monkeypatch.setattr(match, "model_thresholds",
                        lambda: {"rerank_logit": -10.0, "cosine": 0.15, "title_similarity": 0.0})
    rows = [cand("1", 1, -3.608191, 0.146531, "Naxia", 1.0)]
    decision = match.decide({}, rows, "model")
    assert decision["status"] == "rejected"
    assert decision["reason"] == "cosine 0.146531 < 0.15"


def test_model_scores_shortens_the_query_after_http_422():
    from nemotron_challenge.clients import ServiceError

    class Retrieval:
        def __init__(self):
            self.lengths = []

        def embed(self, inputs, input_type):
            if input_type == "query":
                self.lengths.append(len(inputs[0]))
                if len(inputs[0]) > 700:
                    raise ServiceError("too many tokens", status_code=422)
            return [[1.0] + [0.0] * 2047 for _ in inputs]

        def rerank(self, query, documents):
            return [{"index": i, "relevance_score": -float(i)} for i in range(len(documents))]

    retrieval = Retrieval()
    rows = [{"title": "A", "excerpt": "a"}, {"title": "B", "excerpt": "b"}]
    used = match.model_scores(retrieval, {"headword": "X", "text": "1 2 3 " * 600}, rows)
    assert used == 700 and retrieval.lengths == [1500, 700]
    assert rows[0]["rerank_position"] == 1 and rows[0]["cosine"] == 1.0


def test_retry_backs_off_after_http_429(monkeypatch):
    from nemotron_challenge import common
    from nemotron_challenge.clients import ServiceError

    sleeps, calls = [], []
    monkeypatch.setattr(common.time, "sleep", sleeps.append)

    def busy():
        calls.append(1)
        if len(calls) < 4:
            raise ServiceError("busy", status_code=429, retry_after="1")
        return "ok"

    assert common.with_retry(busy) == "ok"
    assert sleeps == [2.0, 4.0, 8.0]
