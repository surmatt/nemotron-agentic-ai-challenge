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


def test_model_choice_needs_logit_margin_and_cosine():
    rows = [cand("1", 1, 1.0, 0.4), cand("2", 2, 0.2, 0.3)]
    assert calibrate.model_choice(rows, 0.0, 0.5, 0.2) == "1"
    assert calibrate.model_choice(rows, 0.0, 1.0, 0.2) is None  # margin 0.8 is too small
    assert calibrate.model_choice(rows, 0.0, 0.5, 0.5) is None  # cosine too low
    assert calibrate.model_choice([cand("1", 1, -3.0, 0.4)], -5.0, 9.0, 0.0) == "1"  # one candidate: no margin test
    assert calibrate.model_choice(rows, 0.0, 0.5, 0.2, title=0.75) is None  # title similarity 0.0 < 0.75


def test_match_uses_the_calibrated_threshold_file(tmp_path, monkeypatch):
    path = tmp_path / "match_thresholds.json"
    path.write_text(json.dumps({"rerank_logit": -10.0, "margin": 0.5, "cosine": 0.15, "title_similarity": 0.0}))
    monkeypatch.setattr(match, "THRESHOLD_FILE", path)
    rows = [cand("1", 1, -2.0, 0.3, "Heat", 1.0), cand("2", 2, -2.4, 0.2)]
    decision = match.decide({}, rows, "model")
    assert decision["status"] == "rejected" and decision["thresholds"]["margin"] == 0.5  # margin 0.4
    rows[1]["rerank_logit"] = -3.0
    assert match.decide({}, rows, "model")["status"] == "accepted"
    monkeypatch.setattr(match, "THRESHOLD_FILE", tmp_path / "missing.json")
    assert match.model_thresholds() == {"rerank_logit": match.RERANK_ACCEPT, "margin": 0.0, "cosine": match.COSINE_ACCEPT,
                                        "title_similarity": match.MODEL_TITLE_ACCEPT}


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
