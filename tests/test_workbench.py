"""Fixture tests for the visual workbench. Stub clients replace Parse, Super VL, and Wikipedia.

They prove the step wiring, storage layout, and API contract. They do not prove OCR or match quality.
"""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from nemotron_challenge import match, workbench  # noqa: E402
from nemotron_challenge.common import sha256_text  # noqa: E402
from nemotron_challenge.config import PARSE_MODEL, SUPER_MODEL, Settings  # noqa: E402
from nemotron_challenge.ui_server import create_app  # noqa: E402

BODY = "HEAT, in physiology, one of the sensible qualities of bodies, produced by fire. " * 4
PARSE_CONTENT = (
    "<x_0.40><y_0.01>HEA<x_0.60><y_0.03><class_Page-header>\n\n"
    f"<x_0.05><y_0.10>{BODY}<x_0.95><y_0.40><class_Text>\n\n"
    "<x_0.05><y_0.45>A figure<x_0.95><y_0.60><class_Picture>\n\n"
    "<x_0.48><y_0.96>853<x_0.52><y_0.98><class_Page-footer>"
)
ARTICLE_TEXT = "Heat is energy in transfer. Heat moves from hotter bodies to colder bodies. " * 5


def png(size=(400, 600), fmt="PNG") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, "white").save(buffer, format=fmt)
    return buffer.getvalue()


class FakeParse:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def parse(self, image_data_url, instruction, max_tokens):
        assert image_data_url.startswith("data:image/png;base64,")
        return {"model": PARSE_MODEL, "choices": [{"message": {"content": PARSE_CONTENT}, "finish_reason": "stop"}]}


class FakeChat(FakeParse):
    model = SUPER_MODEL

    def request(self, method, path, payload):
        assert payload["chat_template_kwargs"] == {"enable_thinking": False}
        text = BODY.replace("physiology", "phyfiology")
        return {"model": SUPER_MODEL, "usage": {"completion_tokens": 50},
                "choices": [{"message": {"content": text}, "finish_reason": "stop"}]}


class FakeWiki(FakeParse):
    def search(self, query, top_k, excerpt_chars):
        hit = SimpleNamespace(page_id="42", revision_id="7", title="Heat", url="https://en.wikipedia.org/wiki/Heat",
                              excerpt=ARTICLE_TEXT[:200], excerpt_offset=0, total_chars=len(ARTICLE_TEXT), rank=1,
                              bm25_score=9.5)
        return SimpleNamespace(hits=[hit])

    def article(self, page_id, offset, max_chars):
        provenance = SimpleNamespace(revision_url="https://en.wikipedia.org/w/index.php?oldid=7",
                                     dataset_revision="rev", text_sha256=sha256_text(ARTICLE_TEXT))
        return SimpleNamespace(page_id=page_id, revision_id="7", title="Heat", url="https://en.wikipedia.org/wiki/Heat",
                               provenance=provenance, license={"spdx": "CC-BY-SA-4.0"}, text=ARTICLE_TEXT,
                               next_offset=None)


@pytest.fixture
def stubs(monkeypatch):
    monkeypatch.setattr(workbench, "ParseClient", FakeParse)
    monkeypatch.setattr(workbench, "ChatClient", FakeChat)
    monkeypatch.setattr(match, "WikiClient", FakeWiki)
    monkeypatch.setattr(match, "retrieval_mode", lambda settings: ("lexical", "test: no retrieval service"))
    monkeypatch.setattr(workbench.site_stage, "compile_latex", fake_compile)


def fake_compile(tex_dir):
    for source in tex_dir.glob("*.tex"):
        source.with_suffix(".pdf").write_bytes(b"%PDF-1.5 test")
    return {"engine": "tectonic test", "compiled": 1, "failed": []}


def test_prepare_image_keeps_png_and_converts_other_formats():
    data = png()
    kept, ext, info = workbench.prepare_image(data)
    assert kept == data and ext == "png" and info["converted"] is False
    converted, ext, info = workbench.prepare_image(png(fmt="TIFF"))
    assert ext == "jpg" and info["converted"] is True and info["conversion"]["reasons"] == ["format"]
    assert converted[:2] == b"\xff\xd8"
    with pytest.raises(workbench.StepError):
        workbench.prepare_image(b"not an image")


def test_upload_is_stored_once_with_checksums(tmp_path):
    first = workbench.create_upload(tmp_path, png(), "../evil name?.png")
    assert workbench.create_upload(tmp_path, png(), "again.png") == first
    meta = workbench.read_json(tmp_path / "ui" / "uploads" / first / "meta.json")
    assert meta["filename"] == "evil name_.png" and meta["scan_sha256"].startswith(first)
    assert meta["source"]["kind"] == "upload"
    with pytest.raises(workbench.StepError):
        workbench.upload_dir(tmp_path, "../../etc")


def test_steps_run_in_order_and_keep_raw_replies(tmp_path, stubs):
    upload_id = workbench.create_upload(tmp_path, png(), "heat.png")
    folder = tmp_path / "ui" / "uploads" / upload_id
    settings = Settings()
    for step in workbench.STEPS:
        workbench.run_step(settings, folder, step)
        assert workbench.load_state(folder)["steps"][step]["status"] == "done", workbench.load_state(folder)
    assert (folder / "extract" / "raw.json").is_file() and (folder / "correct" / "raw" / "b01.json").is_file()
    view = workbench.upload_view(tmp_path, upload_id)
    assert [b["cls"] for b in view["page"]["furniture"]] == ["Page-header", "Page-footer"]
    text_block = next(b for b in view["page"]["blocks"] if b["cls"] == "Text")
    # The long-s rule repairs "phyfiology" in the Super VL text, so the used text equals the Parse text here.
    assert text_block["text_source"] == "super_vl" and text_block["long_s_rule_changed"] is True
    assert text_block["diff"] == [{"op": "equal", "text": " ".join(BODY.split())}]
    [entry] = view["entries"]
    assert entry["headword"] == "HEAT" and entry["match"]["decision"]["status"] == "accepted"
    assert entry["match"]["searches_complete"] is True
    assert [s["kind"] for s in entry["match"]["searches"]] == ["headword", "headword + keywords"]
    assert entry["match"]["search_terms"]["llm"]["status"] == "skipped"
    assert entry["match"]["searches"][0]["hits"][0] | {"status": "candidate"} == entry["match"]["searches"][0]["hits"][0]
    assert entry["match"]["article"]["revision_id"] == "7" and entry["pair"]["article"]["page_id"] == "42"
    assert view["steps"]["compare"]["summary"]["pairs"] == 1


def test_rerun_moves_earlier_outputs_to_history(tmp_path, stubs):
    upload_id = workbench.create_upload(tmp_path, png(), "heat.png")
    folder = tmp_path / "ui" / "uploads" / upload_id
    for step in ("extract", "correct"):
        workbench.run_step(Settings(), folder, step)
    workbench.run_step(Settings(), folder, "extract")
    [stamp] = [p.name for p in (folder / "history").iterdir()]
    assert (folder / "history" / stamp / "correct" / "page.json").is_file()
    assert workbench.load_state(folder)["steps"]["correct"]["status"] == "idle"


def wait(upload_id):
    thread = workbench._RUNNING.get(upload_id)
    if thread:
        thread.join(timeout=30)


def legacy_model_upload(tmp_path):
    upload_id = workbench.create_upload(tmp_path, png(), "heat.png")
    folder = tmp_path / "ui" / "uploads" / upload_id
    for step in workbench.STEPS:
        workbench.run_step(Settings(), folder, step)
    [record] = workbench.read_json(folder / "match" / "matches.json")
    saved = workbench.read_json(folder / "match" / "candidates" / f"{record['entry_id']}.json")
    top = {**saved["candidates"][0], "rerank_position": 1, "rerank_logit": -2.424185, "cosine": 0.424879}
    second = {**top, "page_id": "43", "title": "Heat transfer", "rerank_position": 2, "rerank_logit": -2.690706}
    record.pop("article")
    record["mode"] = "model"
    record["decision"] = {"status": "rejected", "reason": "margin < 0.5",
                          "thresholds": {"rerank_logit": -10.0, "margin": 0.5, "cosine": 0.15,
                                         "title_similarity": 0.0}}
    workbench.write_json(folder / "match" / "matches.json", [record])
    workbench.write_json(folder / "match" / "candidates" / f"{record['entry_id']}.json",
                         {**record, "candidates": [top, second]})
    workbench.write_json(folder / "match" / "terms" / f"{record['entry_id']}.json", {"response": "unchanged"})
    workbench.write_json(folder / "compare" / "pairs.json", [])
    return upload_id, folder


def test_reapply_match_updates_real_decisions_and_downstream_without_model_calls(tmp_path, stubs, monkeypatch):
    upload_id, folder = legacy_model_upload(tmp_path)
    before = (folder / "match" / "matches.json").read_bytes()

    def no_models(*args, **kwargs):
        raise AssertionError("cached scores must not repeat search or model calls")

    monkeypatch.setattr(match, "retrieval_mode", no_models)
    monkeypatch.setattr(match, "match_entry", no_models)
    monkeypatch.setattr(FakeWiki, "search", no_models)
    client = TestClient(create_app(tmp_path, tmp_path / "scans", settings_loader=Settings))
    response = client.post(f"/api/uploads/{upload_id}/reapply-match")
    assert response.status_code == 200 and response.json()["started"] == ["match", "compare", "document"]
    wait(upload_id)
    view = client.get(f"/api/uploads/{upload_id}").json()
    assert all(view["steps"][s]["status"] == "done" for s in workbench.STEPS), view["steps"]
    [entry] = view["entries"]
    assert entry["match"]["decision"]["status"] == "accepted"
    assert entry["match"]["article"]["page_id"] == "42" and entry["pair"]["article"]["page_id"] == "42"
    assert "margin" not in entry["match"]["decision"]["thresholds"]
    summary = view["steps"]["match"]["summary"]
    assert summary["scores_reused"] is True and summary["accepted"] == 1
    old = folder / "history" / view["steps"]["match"]["archived_previous"] / "match"
    assert (old / "matches.json").read_bytes() == before
    assert (old / "terms" / "E0001.json").read_bytes() == (folder / "match" / "terms" / "E0001.json").read_bytes()
    saved = workbench.read_json(folder / "match" / "candidates" / "E0001.json")
    assert saved["decision"]["status"] == "accepted" and saved["decision_reapplied_at"]
    assert saved["candidates"] == workbench.read_json(old / "candidates" / "E0001.json")["candidates"]


@pytest.mark.parametrize("invalid", ["changed_text", "missing_scores", "lexical"])
def test_reapply_refuses_invalid_cached_scores_without_touching_saved_outputs(tmp_path, stubs, invalid):
    upload_id, folder = legacy_model_upload(tmp_path)
    path = folder / "match" / "candidates" / "E0001.json"
    saved = workbench.read_json(path)
    if invalid == "changed_text":
        saved["entry_text_sha256"] = "different"
    elif invalid == "missing_scores":
        saved["candidates"][0].pop("rerank_logit")
    else:
        saved["mode"] = "lexical"
    workbench.write_json(path, saved)
    before = path.read_bytes()
    state = (folder / "state.json").read_bytes()
    client = TestClient(create_app(tmp_path, tmp_path / "scans", settings_loader=Settings))
    assert client.post(f"/api/uploads/{upload_id}/reapply-match").status_code == 409
    assert path.read_bytes() == before and (folder / "state.json").read_bytes() == state
    assert not (folder / "history").exists()


def test_reapply_does_not_accept_when_article_fetch_fails(tmp_path, stubs, monkeypatch):
    _, folder = legacy_model_upload(tmp_path)
    saved = workbench.read_json(folder / "match" / "candidates" / "E0001.json")
    [entry] = workbench.read_json(folder / "correct" / "entries.json")

    def unavailable(*args, **kwargs):
        raise match.ServiceError("Wikipedia unavailable", status_code=400)

    monkeypatch.setattr(FakeWiki, "article", unavailable)
    result = match.reapply_entry(Settings(), entry, saved, tmp_path / "new", tmp_path / "failures.jsonl")
    assert result["decision"]["status"] == "error" and "article" not in result
    [failure] = workbench.read_jsonl(tmp_path / "failures.jsonl")
    assert failure["step"] == "reapply" and failure["error"] == "Wikipedia unavailable"


def test_reapply_checks_full_article_for_list_pages(tmp_path, stubs, monkeypatch):
    _, folder = legacy_model_upload(tmp_path)
    saved = workbench.read_json(folder / "match" / "candidates" / "E0001.json")
    [entry] = workbench.read_json(folder / "correct" / "entries.json")
    article = FakeWiki.article

    def full_text(self, page_id, offset, max_chars):
        result = article(self, page_id, offset, max_chars)
        result.text = "Heat may refer to: several meanings." if page_id == "42" else ARTICLE_TEXT
        result.provenance.text_sha256 = sha256_text(result.text)
        return result

    monkeypatch.setattr(FakeWiki, "article", full_text)
    result = match.reapply_entry(Settings(), entry, saved, tmp_path / "new", tmp_path / "failures.jsonl")
    assert result["decision"]["status"] == "accepted" and result["article"]["page_id"] == "43"
    assert result["list_pages_removed_after_fetch"] == [{"page_id": "42", "title": "Heat"}]


def test_rerun_includes_later_steps_that_ran():
    statuses = {"extract": "done", "correct": "idle", "match": "done", "compare": "failed", "document": "idle"}
    assert workbench.rerun_steps(statuses, "extract") == ["extract", "match", "compare"]
    assert workbench.rerun_steps(statuses, "compare") == ["compare"]
    with pytest.raises(workbench.StepError):
        workbench.rerun_steps(statuses, "agent")


def test_upload_rerun_runs_later_steps_again(tmp_path, stubs):
    upload_id = workbench.create_upload(tmp_path, png(), "heat.png")
    folder = tmp_path / "ui" / "uploads" / upload_id
    for step in workbench.STEPS:
        workbench.run_step(Settings(), folder, step)
    assert workbench.rerun(tmp_path, upload_id, "correct", Settings) == ["correct", "match", "compare", "document"]
    wait(upload_id)
    state = workbench.load_state(folder)["steps"]
    assert all(state[s]["status"] == "done" for s in workbench.STEPS), state
    assert state["correct"]["archived_previous"]
    [stamp] = [p.name for p in (folder / "history").iterdir()]
    assert {p.name for p in (folder / "history" / stamp).iterdir()} >= {"correct", "match", "compare", "document"}


def test_document_step_writes_latex_and_pdf(tmp_path, stubs):
    client = TestClient(create_app(tmp_path, tmp_path / "scans", settings_loader=Settings))
    upload_id = workbench.create_upload(tmp_path, png(), "heat.png")
    folder = tmp_path / "ui" / "uploads" / upload_id
    for step in ("extract", "correct", "document"):
        workbench.run_step(Settings(), folder, step)
    view = client.get(f"/api/uploads/{upload_id}").json()
    summary = view["steps"]["document"]["summary"]
    assert view["steps"]["document"]["status"] == "done" and summary["pdf"] and summary["entry_text"] == "correct"
    doc = view["document"]
    assert "Uploaded scan heat.png" in doc["tex"] and "\\item[Dataset]" not in doc["tex"]
    assert "HEAT (E0001)" in doc["tex"] and "correct/raw/b*.json" in doc["tex"]
    assert client.get(doc["pdf_url"]).headers["content-type"] == "application/pdf"
    assert client.get(doc["tex_url"]).text == doc["tex"]
    assert client.get(f"/api/uploads/{upload_id}/document/exe").status_code == 409


def test_document_step_records_a_latex_failure(tmp_path, stubs, monkeypatch):
    monkeypatch.setattr(workbench.site_stage, "compile_latex",
                        lambda tex_dir: {"engine": "t", "compiled": 0, "failed": [{"file": "scan.tex", "error": "! Undefined"}]})
    upload_id = workbench.create_upload(tmp_path, png(), "heat.png")
    folder = tmp_path / "ui" / "uploads" / upload_id
    for step in ("extract", "document"):
        workbench.run_step(Settings(), folder, step)
    state = workbench.load_state(folder)["steps"]["document"]
    assert state["status"] == "failed" and "Undefined" in state["error"]
    assert (folder / "document" / "scan.tex").is_file()


def corpus_fixture(tmp_path, monkeypatch):
    """A one-scan corpus with a saved extract, match, and compare run."""
    data = png()
    item = {"row_index": 7, "page_id": "britannica:test:7", "filename": "page-0007-test.png",
            "image_sha256": workbench.sha256_bytes(data), "volume_id": "v1"}
    monkeypatch.setattr(workbench, "load_manifest", lambda: {"dataset": "test", "revision": "r1", "license": "x",
                                                             "pages": [item]})
    scans = tmp_path / "scans"
    scans.mkdir()
    (scans / item["filename"]).write_bytes(data)
    work = tmp_path / "artifacts"
    raw = {"page_id": item["page_id"], "filename": item["filename"], "image_sha256": item["image_sha256"],
           "model": PARSE_MODEL, "elapsed_seconds": 1.5,
           "response": {"model": PARSE_MODEL,
                        "choices": [{"message": {"content": PARSE_CONTENT}, "finish_reason": "stop"}]}}
    workbench.write_json(work / "extract" / "raw" / "page-0007-test.json", raw)
    page = workbench.extract_stage.derive_page(item, raw)
    for name, rows in (("pages", [page]), ("entries", workbench.extract_stage.segment([page]))):
        for row in rows:
            workbench.append_jsonl(work / "extract" / f"{name}.jsonl", row)
    for stage in ("extract", "match", "compare"):
        workbench.write_json(work / stage / "summary.json", {"finished_at": "2026-10-18T13:00:00+00:00"})
    return work, scans


def test_corpus_rerun_reuses_saved_parse_reply(tmp_path, monkeypatch, stubs):
    class NoParse(FakeParse):
        def parse(self, *args):
            raise AssertionError("the saved Parse reply must be reused")

    monkeypatch.setattr(workbench, "ParseClient", NoParse)
    work, scans = corpus_fixture(tmp_path, monkeypatch)
    client = TestClient(create_app(work, scans, settings_loader=Settings))
    reply = client.post("/api/corpus/7/rerun", json={"step": "match"}).json()
    assert reply["seeded"] == ["extract"] and reply["started"] == ["match", "compare"]
    wait(reply["id"])
    view = client.get(f"/api/uploads/{reply['id']}").json()
    assert view["steps"]["extract"]["seeded_from"]["path"].endswith("page-0007-test.json")
    assert view["steps"]["correct"]["status"] == "idle"
    assert view["steps"]["compare"]["status"] == "done" and view["entries"][0]["pair"]
    folder = work / "ui" / "uploads" / reply["id"]
    assert (folder / "extract" / "raw.json").read_bytes() == (work / "extract" / "raw" / "page-0007-test.json").read_bytes()
    assert view["page"]["page_id"] == f"upload:{reply['id']}"

    again = client.post("/api/corpus/7/rerun", json={"step": "compare"}).json()
    assert again["id"] == reply["id"] and again["started"] == ["match", "compare"]
    wait(again["id"])
    assert len(list((folder / "history").iterdir())) == 1
    assert client.post("/api/corpus/7/rerun", json={"step": "nope"}).status_code == 409


def test_corpus_document_and_static_site_routes(tmp_path, monkeypatch):
    work, scans = corpus_fixture(tmp_path, monkeypatch)
    workbench.write_text(work / "site" / "latex" / "page-0007-test.tex", "\\documentclass{article}")
    workbench.write_text(work / "site" / "index.html", "<h1>site</h1>")
    workbench.write_json(work / "site" / "summary.json", {"finished_at": "2026-10-18T14:00:00+00:00"})
    client = TestClient(create_app(work, scans, settings_loader=Settings))
    view = client.get("/api/corpus/7").json()
    assert view["steps"]["document"]["status"] == "done"
    assert view["document"]["pdf_url"] is None and view["document"]["tex"] == "\\documentclass{article}"
    assert client.get("/api/corpus/7/document/tex").text == "\\documentclass{article}"
    assert client.get("/api/corpus/7/document/pdf").status_code == 404
    assert client.get("/api/site").json()["built"] is True
    assert client.get("/site/index.html").text == "<h1>site</h1>"
    assert client.get("/site/").text == "<h1>site</h1>"
    assert client.get("/site/..%2F..%2Fscans%2Fpage-0007-test.png").status_code == 404


def test_failed_model_call_is_recorded(tmp_path, monkeypatch):
    class Broken(FakeParse):
        def parse(self, *args):
            raise workbench.ServiceError("service returned HTTP 503", status_code=503)

    monkeypatch.setattr(workbench, "ParseClient", Broken)
    monkeypatch.setattr("nemotron_challenge.common.time.sleep", lambda seconds: None)
    upload_id = workbench.create_upload(tmp_path, png(), "heat.png")
    folder = tmp_path / "ui" / "uploads" / upload_id
    workbench.run_step(Settings(), folder, "extract")
    state = workbench.load_state(folder)["steps"]["extract"]
    assert state["status"] == "failed" and "503" in state["error"]
    assert "503" in (folder / "failures.jsonl").read_text()


def test_api_upload_run_all_and_views(tmp_path, stubs):
    client = TestClient(create_app(tmp_path, tmp_path / "scans", settings_loader=Settings))
    assert client.post("/api/uploads", files={"file": ("x.txt", b"hello", "text/plain")}).status_code == 409
    upload_id = client.post("/api/uploads", files={"file": ("heat.png", png(), "image/png")}).json()["id"]
    assert client.post(f"/api/uploads/{upload_id}/run", json={"steps": ["match"]}).status_code == 409
    assert client.post(f"/api/uploads/{upload_id}/run", json={"all": True}).json()["started"] == list(workbench.STEPS)
    thread = workbench._RUNNING.get(upload_id)
    if thread:
        thread.join(timeout=30)
    view = client.get(f"/api/uploads/{upload_id}").json()
    assert all(view["steps"][s]["status"] == "done" for s in workbench.STEPS), view["steps"]
    assert client.get(f"/api/uploads/{upload_id}/image?w=128").headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/uploads/{upload_id}/blocks/1/crop").content[:2] == b"\xff\xd8"
    assert client.get(f"/api/uploads/{upload_id}/raw/extract").json()["model"] == PARSE_MODEL
    assert client.get("/api/uploads").json()[0]["steps"]["compare"] == "done"
    assert client.get("/api/uploads/000000000000").status_code == 404


def test_corpus_views_work_without_saved_runs(tmp_path):
    client = TestClient(create_app(tmp_path, tmp_path / "scans", settings_loader=Settings))
    index = client.get("/api/corpus").json()
    assert index["has_artifacts"] is False and len(index["pages"]) == 100
    assert {p["status"] for p in index["pages"]} == {"no_run"}
    row = index["pages"][0]["row_index"]
    view = client.get(f"/api/corpus/{row}").json()
    assert view["page"] is None and view["steps"]["extract"]["status"] == "idle"
    assert client.get("/api/corpus/999999").status_code == 404


def test_match_view_rebuilds_searches_for_older_runs(tmp_path):
    record = {"entry_id": "E0001", "headword": "HEAT", "mode": "model", "queries": ["heat", "heat energy"],
              "query_chars": 20, "entry_text_sha256": "abc", "decision": {"status": "rejected"}}
    rows = [{"page_id": "2", "title": "Warmth", "url": "u2", "best_rank": 1, "excerpt": "",
             "bm25": {"q1": {"rank": 1, "score": 3.0}}},
            {"page_id": "1", "title": "Heat", "url": "u1", "best_rank": 2, "excerpt": "",
             "bm25": {"q0": {"rank": 1, "score": 9.0}, "q1": {"rank": 2, "score": 2.0}}}]
    workbench.write_json(tmp_path / "E0001.json", {**record, "candidates": rows})
    entry = {"entry_id": "E0001", "headword": "HEAT", "text": "HEAT is a quality of bodies.", "text_sha256": "abc"}
    view = workbench.match_view(record, tmp_path / "E0001.json", tmp_path, entry)
    assert view["searches_complete"] is False
    assert [[h["title"] for h in s["hits"]] for s in view["searches"]] == [["Heat"], ["Warmth", "Heat"]]
    assert view["model_query"]["text"] == "HEAT. HEAT is a qual" and view["model_query"]["documents"] == 2
    changed = workbench.match_view(record, tmp_path / "E0001.json", tmp_path, {**entry, "text_sha256": "new"})
    assert changed["model_query"]["text"] is None and changed["model_query"]["note"]


def test_word_diff_marks_changes():
    ops = workbench.word_diff("the phyfiology of heat", "the physiology of heat")
    assert ops == [{"op": "equal", "text": "the"}, {"op": "delete", "text": "phyfiology"},
                   {"op": "insert", "text": "physiology"}, {"op": "equal", "text": "of heat"}]


def test_services_reports_configuration_without_network():
    result = workbench.services(Settings(retrieval_base_url=""), live=False)
    assert result["services"]["retrieval"] == {"configured": False, "status": "missing"}
    assert Path(workbench.__file__).name == "workbench.py"
