"""Fixture tests for the Super VL correction stage and the OCR metrics. They prove the rules, not OCR quality."""
import json
from pathlib import Path

import pytest

from nemotron_challenge import correct, ocr_eval
from nemotron_challenge.config import SUPER_MODEL


def test_normalise_applies_the_transcription_rules():
    text = "The fun is ſhining;  pro-\nmoted — “ok” fœtidus *Black Hole*"
    assert ocr_eval.normalise(text) == 'the fun is shining; promoted - "ok" foetidus black hole'
    assert ocr_eval.normalise("Μερόῃ ἱερῶν") == "μεροη ιερων"


def test_error_rates_count_edits_and_words_not_in_reference():
    rates = ocr_eval.error_rates("the sun is hot", "the fun is hot hot")
    assert rates["char_edits"] == 5 and rates["word_edits"] == 2
    assert rates["words_not_in_reference"] == 1 and rates["examples_not_in_reference"] == ["fun"]
    assert ocr_eval.error_rates("abc", "abc")["cer"] == 0.0


def test_long_s_rule_changes_only_non_words():
    vocabulary = {"persons", "sun", "fun", "soft"}
    assert ocr_eval.fix_long_s("Perfons in the fun, foft", vocabulary) == "Persons in the fun, soft"


def page(row, n):
    blocks = [{"index": i, "cls": "Text", "bbox": [0.1, 0.1 * i, 0.5, 0.1 * i + 0.08], "text": "x" * 200}
              for i in range(n)]
    return {"page_id": f"p{row}", "row_index": row, "filename": f"page-{row}.jpg", "status": "ok", "blocks": blocks}


def test_gold_selection_is_fixed_and_skips_the_probe_scan():
    pages = [page(row, 3) for row in range(1000, 1040)] + [page(1032, 5)]
    first, second = ocr_eval.select_gold(pages), ocr_eval.select_gold(list(reversed(pages)))
    assert first == second and len(first) == 30
    assert 1032 not in {g["row_index"] for g in first}
    assert [g["gold_id"] for g in first[:2]] == ["G01", "G02"]


def test_crop_block_cuts_the_box_with_margin_and_enlarges(tmp_path):
    from PIL import Image

    scan = tmp_path / "scan.jpg"
    Image.new("RGB", (600, 800), "white").save(scan)
    out = tmp_path / "crop.jpg"
    ocr_eval.crop_block(scan, [0.1, 0.1, 0.5, 0.2], out, pad=6, scale=3)
    with Image.open(out) as crop:
        assert crop.size == ((240 + 12) * 3, (80 + 12) * 3)


def test_instruction_has_parse_text_except_for_the_image_only_variant():
    block = {"bbox": [0.1, 0.2, 0.3, 0.4], "text": "Under the article fire"}
    assert "Under the article fire" in correct.instruction("crop_nothink", block)
    assert "Under the article fire" not in correct.instruction("crop_noparse", block)
    assert "x0=0.100" in correct.instruction("page_nothink", block)
    assert correct.request_body("crop_think", block, b"x").get("chat_template_kwargs") is None
    assert correct.request_body("crop_nothink", block, b"x")["chat_template_kwargs"] == {"enable_thinking": False}


@pytest.mark.parametrize("bbox,record,expected", [
    ([0.5, 0.1, 0.52, 0.2], {"corrected_text": ""}, ("parse_fallback", "box_too_small")),
    ([0.1, 0.1, 0.5, 0.2], None, ("parse_fallback", "super_vl_failed")),
    ([0.1, 0.1, 0.5, 0.2], {"corrected_text": "y" * 400}, ("super_vl", "expanded_beyond_parse")),
    ([0.1, 0.1, 0.5, 0.2], {"corrected_text": ""}, ("super_vl", "emptied")),
    ([0.1, 0.1, 0.5, 0.2], {"corrected_text": "x" * 210}, ("super_vl", None)),
])
def test_text_decision_rules(bbox, record, expected):
    block = {"cls": "Text", "bbox": bbox, "text": "x" * 200}
    assert correct.decide_text(block, record, True) == expected
    assert correct.decide_text({**block, "cls": "Table"}, record, True) == ("parse", None)


class FakeClient:
    model = SUPER_MODEL

    def __init__(self, content, finish="stop", model=SUPER_MODEL):
        self.reply = {"model": model, "choices": [{"finish_reason": finish, "message": {"content": content}}],
                      "usage": {"completion_tokens": 5, "completion_tokens_details": {"reasoning_tokens": 0}}}
        self.payloads = []

    def request(self, method, path, payload):
        self.payloads.append(payload)
        return self.reply


@pytest.fixture
def scan(tmp_path):
    from PIL import Image

    path = tmp_path / "page-0001.jpg"
    Image.new("RGB", (600, 800), "white").save(path)
    return path


def test_correct_block_saves_the_unchanged_reply_and_maps_empty(tmp_path, scan):
    block = {"index": 3, "bbox": [0.1, 0.1, 0.5, 0.2], "text": "fome text"}
    out = tmp_path / "raw.json"
    record = correct.correct_block(FakeClient("EMPTY"), "crop_nothink", scan, {"page_id": "p1"}, block, out)
    saved = json.loads(out.read_text())
    assert record["corrected_text"] == "" and saved["response"]["choices"][0]["message"]["content"] == "EMPTY"
    assert saved["parse_text"] == "fome text" and saved["request"]["chat_template_kwargs"]["enable_thinking"] is False
    again = correct.correct_block(FakeClient("other"), "crop_nothink", scan, {"page_id": "p1"}, block, out)
    assert again["corrected_text"] == ""  # A saved reply is reused, not replaced.


@pytest.mark.parametrize("client", [FakeClient("text", finish="length"), FakeClient("text", model="other/model")])
def test_correct_block_rejects_incomplete_or_wrong_model_replies(tmp_path, scan, client):
    block = {"index": 0, "bbox": [0.1, 0.1, 0.5, 0.2], "text": "t"}
    with pytest.raises(ValueError):
        correct.correct_block(client, "crop_nothink", scan, {"page_id": "p1"}, block, tmp_path / "raw.json")
    assert not (tmp_path / "raw.json").exists()


def test_gold_file_matches_the_selection_rules():
    gold = json.loads((Path(__file__).resolve().parents[1] / "docs" / "evaluation" / "ocr_gold.json").read_text())
    blocks = gold["blocks"]
    assert len(blocks) == 30 and len({b["row_index"] for b in blocks}) == 15
    assert all(b["cls"] in ocr_eval.TEXT_CLASSES and b["row_index"] != 1032 for b in blocks)
    assert sum(b["text"] is None for b in blocks) == 1


def test_later_stages_prefer_corrected_text_when_it_exists(tmp_path):
    from nemotron_challenge.common import text_dir

    (tmp_path / "extract").mkdir()
    (tmp_path / "extract" / "entries.jsonl").write_text("")
    assert text_dir(tmp_path).name == "extract"
    (tmp_path / "correct").mkdir()
    (tmp_path / "correct" / "entries.jsonl").write_text("")
    assert text_dir(tmp_path).name == "correct"
