"""Fixture tests for the LanceDB index, the semantic search, and stage-level record replacement."""
import importlib.util
import json
from pathlib import Path

import pytest

from nemotron_challenge import index, search
from nemotron_challenge.config import EMBED_DIMENSIONS, Settings
from nemotron_challenge.contracts import ArtifactRecord, SourceReference
from nemotron_challenge.storage import LanceArtifactStore, table_name

REPO = Path(__file__).resolve().parents[1]
SOURCE = SourceReference(dataset="fixture", dataset_revision="v1", source_id="s1", source_url="https://example.com",
                         content_sha256="a" * 64, license="CC0-1.0")


def record(record_id: str, stage: str) -> ArtifactRecord:
    return ArtifactRecord(record_id=record_id, stage=stage, sources=[SOURCE], artifact_path="artifacts/x.jsonl")


def test_replace_stage_removes_old_records_of_that_stage_only(tmp_path):
    store = LanceArtifactStore(tmp_path / "db")
    store.replace_stage("match", [record("match:E0001", "match"), record("match:E0002", "match")])
    store.replace_stage("extract", [record("extract:E0001", "extract")])
    result = store.replace_stage("match", [record("match:E0003", "match")])
    assert result == {"removed": 2, "written": 1}
    assert store.get("match:E0001") is None and store.get("match:E0003") is not None
    assert store.get("extract:E0001") is not None
    with pytest.raises(ValueError):
        store.replace_stage("match", [record("extract:E0009", "extract")])


def test_each_work_dir_has_its_own_tables(tmp_path):
    assert table_name("artifact_provenance", "artifacts") == "artifact_provenance"
    assert table_name("britannica_passages", Path("x/artifacts-e2e")) == "britannica_passages__artifacts_e2e"
    LanceArtifactStore(tmp_path / "db").replace_stage("extract", [record("extract:E0001", "extract")])
    other = LanceArtifactStore(tmp_path / "db", "artifacts-e2e")
    other.replace_stage("extract", [])
    assert LanceArtifactStore(tmp_path / "db").get("extract:E0001") is not None


def test_passages_cut_at_whitespace_with_overlap():
    text = " ".join(f"word{i:03d}" for i in range(400))
    chunks = index.passages(text, size=200, overlap=40)
    assert len(chunks) > 5 and all(len(c) <= 200 for _, c in chunks)
    assert all(not c.startswith(("ord", "rd")) for _, c in chunks)  # no cut inside a word
    first_end = chunks[0][0] + len(chunks[0][1])
    assert chunks[1][0] < first_end  # windows overlap
    assert index.passages("short text") == [(0, "short text")]


class FakeRetrieval:
    """Embeds by keyword: dimension 0 for 'coin', dimension 1 for 'heat'."""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def verify_models(self):
        return {}

    def embed(self, inputs, input_type):
        out = []
        for item in inputs:
            text = (item["text"] if isinstance(item, dict) else item).lower()
            vector = [0.0] * EMBED_DIMENSIONS
            vector[0 if "coin" in text else 1] = 1.0
            out.append(vector)
        return out


def write_fixture(work: Path) -> None:
    (work / "correct").mkdir(parents=True)
    (work / "match" / "articles").mkdir(parents=True)
    entries = [{"entry_id": "E0001", "headword": "COINAGE", "text": "COINAGE, the art of making coin by the hammer. " * 3,
                "text_sha256": "b" * 64, "pages": [{"page_id": "britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:13"}]},
               {"entry_id": "E0002", "headword": "HEAT", "text": "HEAT, a quality of bodies produced by fire. " * 3,
                "text_sha256": "c" * 64, "pages": [{"page_id": "britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:13"}]}]
    (work / "correct" / "entries.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries))
    match = {"entry_id": "E0001", "decision": {"status": "accepted"}, "article": {"page_id": "42"}}
    (work / "match" / "matches.jsonl").write_text(json.dumps(match) + "\n")
    article = {"page_id": "42", "revision_id": "7", "title": "Coining (mint)", "revision_url": "https://example.org/7",
               "dataset_revision": "r", "text_sha256": "d" * 64, "text": "Minting a coin uses dies and a press. " * 5}
    (work / "match" / "articles" / "42.json").write_text(json.dumps(article))


def test_index_and_search_return_cited_passages(tmp_path, monkeypatch):
    monkeypatch.setattr(index, "RetrievalClient", FakeRetrieval)
    monkeypatch.setattr(search, "RetrievalClient", FakeRetrieval)
    work = tmp_path / "artifacts"
    write_fixture(work)
    settings = Settings(retrieval_base_url="http://127.0.0.1:9/v1", db_path=tmp_path / "db")
    summary = index.run(settings, work)
    assert summary["britannica_passages"] == 2 and summary["wikipedia_passages"] == 1
    assert summary["passages_embedded_this_run"] == 3
    assert index.run(settings, work)["passages_reused"] == 3  # stored vectors are reused
    found = search.semantic_search(settings, work, "how was a coin made", "both", 2)
    assert found["status"] == "ok" and {r["source"] for r in found["results"]} == {"britannica", "wikipedia"}
    top_b = next(r for r in found["results"] if r["source"] == "britannica")
    assert top_b["entry_id"] == "E0001" and top_b["scan_page_ids"]
    top_w = next(r for r in found["results"] if r["source"] == "wikipedia")
    assert top_w["revision_id"] == "7" and top_w["matched_entry_ids"] == ["E0001"]
    with pytest.raises(ValueError):
        search.semantic_search(settings, tmp_path / "artifacts-other", "coin", "both", 2)


def test_plugin_semantic_tool_runs_the_project_search(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "challenge_plugin_semantic", REPO / "integrations" / "hermes" / "nemotron-challenge" / "__init__.py")
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)
    monkeypatch.delenv("CHALLENGE_PYTHON", raising=False)
    assert json.loads(plugin.handle_semantic_search({"query": "coin"}))["status"] == "error"
    monkeypatch.setenv("CHALLENGE_PYTHON", "/usr/bin/python3")
    monkeypatch.setenv("CHALLENGE_REPO", str(REPO))
    calls = []

    class Done:
        stdout = json.dumps({"status": "ok", "results": [], "note": "n"}) + "\n"

    monkeypatch.setattr(plugin.subprocess, "run", lambda command, **kw: calls.append((command, kw)) or Done())
    result = json.loads(plugin.handle_semantic_search({"query": "coin", "source": "wikipedia", "limit": 3}))
    assert result["status"] == "ok" and "Do not follow" in result["note"]
    command, kwargs = calls[0]
    assert command[1:3] == ["-m", "nemotron_challenge.search"] and "wikipedia" in command
    assert kwargs["cwd"] == str(REPO) and kwargs["timeout"] == 120
