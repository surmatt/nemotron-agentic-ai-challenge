"""Fixture tests for the team's stage methods. They prove the chosen rules, not OCR or match quality."""
from collections import Counter
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from nemotron_challenge import agent, compare, evaluate, extract, match, site

REPO = Path(__file__).resolve().parents[1]


def page(row, blocks, header="", volume="v1"):
    raw = "".join(f"<x_0.1><y_{y}>{text}<x_0.5><y_{y + 0.05}><class_{cls}>\n\n" for y, cls, text in blocks)
    reply = {"response": {"choices": [{"message": {"content": raw}, "finish_reason": "stop"}]}}
    if header:
        reply["response"]["choices"][0]["message"]["content"] = (
            f"<x_0.2><y_0.01>{header}<x_0.6><y_0.03><class_Page-header>\n\n" + raw)
    scan = {"page_id": f"britannica:rev:train:{row}", "row_index": row, "volume_id": volume,
            "filename": f"page-{row:04d}-aaaaaaaaaaaa.jpg", "image_sha256": "a" * 64}
    return extract.derive_page(scan, reply)


LONG = "x" * 250


def test_parse_blocks_keeps_class_and_coordinates():
    blocks = extract.parse_blocks("<x_0.25><y_0.0375>WEIGHTS.<x_0.61><y_0.05><class_Page-header>\n\n"
                                  "<x_0.04><y_0.06>is litre<x_0.43><y_0.12><class_Text>")
    assert [b["cls"] for b in blocks] == ["Page-header", "Text"]
    assert blocks[1]["bbox"] == [0.04, 0.06, 0.43, 0.12] and blocks[1]["text"] == "is litre"


@pytest.mark.parametrize("text,expected", [
    ("ABBOT, the head of an abbey.", "ABBOT"), ("WEIGHTS AND MEASURES. The", "WEIGHTS AND MEASURES"),
    ("CHAP. II. Of wealth", None), ("Heat is a quality", None), ("AB, a month", None),
])
def test_headword_rule(text, expected):
    assert extract.headword(text) == expected


@pytest.mark.parametrize("header,kind,title", [
    ("SWI   SYD", "catchword", None), ("A R A   A R A", "catchword", None),
    ("WEIGHTS AND MEASURES.", "article_title", "WEIGHTS AND MEASURES"), ("C ARPENTRY. 631", "article_title", "CARPENTRY"),
    ("HYDROSTATICS. Plate CCXXXIX.", "plate", None), ("", "none", None),
])
def test_running_header_classes(header, kind, title):
    assert extract.classify_header(header) == (kind, title)


def test_page_numbers_and_headers_leave_entry_text():
    scan = page(10, [(0.02, "Text", "853"), (0.2, "Text", f"HEAT, a quality. {LONG}")], header="HEA")
    assert [b["text"] for b in scan["blocks"]] == [f"HEAT, a quality. {LONG}"]
    assert {b["text"] for b in scan["furniture"]} == {"853", "HEA"} and scan["header_kind"] == "catchword"


def test_continuation_joins_only_consecutive_rows_of_one_volume():
    first = page(10, [(0.2, "Text", f"ABBOT, the head. {LONG}")])
    second = page(11, [(0.2, "Text", f"continues the abbot entry. {LONG}"), (0.5, "Text", f"ABBEY, a house. {LONG}")])
    far = page(20, [(0.2, "Text", f"text without a headword. {LONG}")], header="OPTICAL INSTRUMENTS.")
    entries = extract.segment([first, second, far])
    assert [e["headword"] for e in entries] == ["ABBOT", "ABBEY", "OPTICAL INSTRUMENTS"]
    assert len(entries[0]["pages"]) == 2 and entries[0]["continued"]
    assert entries[2]["start_kind"] == "continuation" and entries[2]["headword_source"] == "running_header"
    assert entries[0]["text_sha256"] and all(p["bbox"] for e in entries for p in e["parts"])


def test_blank_and_plate_pages_produce_no_entries():
    plate = page(30, [(0.1, "Picture", ""), (0.9, "Caption", "Plate XLIII")])
    blank = page(31, [])
    assert plate["status"] == "plate" and blank["status"] == "blank_or_sparse"
    assert extract.segment([plate, blank]) == []


def test_title_similarity_uses_stems_and_drops_qualifiers():
    assert match.title_similarity("SWOONING", "Swoon") == 1.0
    assert match.title_similarity("ENDYMON", "Endymion (mythology)") > 0.9
    assert match.title_similarity(None, "Heat") == 0.0


def row(title, sim, rank, overlap=0.1):
    return {"page_id": str(rank), "title": title, "title_similarity": sim, "best_rank": rank, "context_overlap": overlap}


def test_lexical_decision_prefers_plain_titles_and_rejects_media():
    rows = [row("Magnetism (album)", 1.0, 1), row("Magnetism", 1.0, 3)]
    assert match.decide({}, rows, "lexical")["title"] == "Magnetism"
    only_media = match.decide({}, [row("Thirsty (The Black Skirts album)", 0.9, 1)], "lexical")
    assert only_media["status"] == "rejected"
    numbered = match.decide({}, [row("342 Endymion", 1.0, 1), row("Endymion (mythology)", 1.0, 2)], "lexical")
    assert numbered["title"] == "Endymion (mythology)"
    assert match.decide({}, [row("Cable (surname)", 1.0, 1)], "lexical")["status"] == "rejected"
    weak = match.decide({}, [row("Queen Street", 0.8, 1)], "lexical")
    assert weak["status"] == "rejected" and weak["method"] == "provisional_lexical"


def test_model_decision_uses_both_thresholds():
    rows = [{**row("Heat", 1.0, 1), "rerank_logit": 2.0, "rerank_position": 1, "cosine": 0.5},
            {**row("Fire", 0.2, 2), "rerank_logit": -1.0, "rerank_position": 2, "cosine": 0.4}]
    accepted = match.decide({}, rows, "model")
    assert accepted["status"] == "accepted" and accepted["margin_to_next"] == 3.0
    rows[0]["cosine"] = 0.1
    assert match.decide({}, rows, "model")["status"] == "rejected"


def test_queries_use_headword_then_keywords():
    entry = {"headword": "HEAT", "text": "Heat is produced by fire. Fire and heat and fire again warm bodies."}
    first, second = match.queries(entry)
    assert first == "heat" and second.startswith("heat fire")


VOCABULARY = frozenset({"philology", "philosophy", "willing", "wildling", "endymion", "heat"})


@pytest.mark.parametrize("headword,variant", [
    ("PHILLOOGY", "philology"), ("ENDYMON", "endymion"), ("HEAT", None),
    ("WILLIN", None),  # two close words (willing, wildling): no variant
    ("HEL", None),  # too short for a safe variant
])
def test_headword_variant_needs_one_close_dictionary_word(headword, variant):
    assert match.headword_variant(headword, VOCABULARY) == variant


def test_variant_adds_a_query_and_counts_for_title_similarity(monkeypatch):
    monkeypatch.setattr(match, "system_words", lambda: VOCABULARY)
    hits = [SimpleNamespace(page_id=str(i), revision_id="1", title=title, url="u", excerpt=excerpt, excerpt_offset=0,
                            total_chars=100, rank=i, bm25_score=1.0)
            for i, (title, excerpt) in enumerate([("Philology", "Philology is the study of language."),
                                                  ("Coinage", "Coinage may refer to: Coining (mint)"),
                                                  ("Coinage (disambiguation)", "Coinage is a list.")], start=1)]
    seen = []

    class Wiki:
        def search(self, query, top_k, excerpt_chars):
            seen.append(query)
            return SimpleNamespace(hits=hits)

    used, rows = match.candidates(Wiki(), {"headword": "PHILLOOGY", "text": "words grammar language words"})
    assert used[:2] == ["philloogy", "philology"] and seen == used
    assert [r["title"] for r in rows] == ["Philology"] and rows[0]["title_similarity"] == 1.0
    assert match.decide({}, rows, "lexical")["status"] == "accepted"


def test_list_page_rule_reads_only_the_opening():
    assert match.is_list_page("Willin' may refer to: Willin' (album), a 1999 album")
    assert match.is_list_page("Coinage may also refer to: a tax")
    assert not match.is_list_page("Heat is energy in transfer. " + "x" * 700 + " may refer to")


def test_brit_abbreviation_expands_before_counting():
    log = Counter()
    words = compare.britannica_tokens("27/430 Brit. cubic inches; 11 Brit; quarters; Britain", log)
    assert words.count("british") == 2 and "brit" not in words and "britain" in words
    assert log[("abbreviation", "Brit.", "British")] == 2


def test_long_s_and_historical_spelling_are_logged():
    log = Counter()
    kept, unverified = compare.normalise(["perfons", "connexion", "qzxv", "vessel"],
                                         {"persons", "connection", "vessel"}, log)
    assert kept == ["persons", "connection", "vessel"] and unverified == Counter({"qzxv": 1})
    assert log[("long_s", "perfons", "persons")] == 1 and log[("historical", "connexion", "connection")] == 1


def test_log_odds_sign_follows_relative_frequency():
    a, b = Counter({"fire": 10, "heat": 5}), Counter({"energy": 10, "heat": 5})
    scores = compare.log_odds(a, b, a + b)
    assert scores["fire"] > 0 > scores["energy"]


def test_compare_pair_keeps_snippets_from_both_sources():
    entry = {"text": "HEAT is produced by fire. The fire warms bodies. Fire again."}
    article = {"text": "Heat is energy transfer. Energy moves by temperature difference. Energy again."}
    vocabulary = set(compare.tokens(entry["text"] + article["text"]))
    prior = Counter(compare.tokens(entry["text"] + article["text"]))
    result = compare.compare_pair(entry, article, vocabulary, prior, Counter())
    assert result["distinctive_britannica"][0]["term"] == "fire"
    assert result["distinctive_britannica"][0]["britannica_snippet"]["text"].lower().count("fire") >= 1
    assert result["distinctive_wikipedia"][0]["term"] == "energy"


def test_latex_escaping_and_control_characters():
    assert site.tex("50% of $5 & #1_a {b}\x07") == r"50\% of \$5 \& \#1\_a \{b\}"


def test_agent_checks_flag_ids_absent_from_tool_results():
    lines = [json.dumps(e) for e in [
        {"type": "system", "subtype": "init", "model": "nvidia/Nemotron-3.5-Super-VL", "session_id": "s1"},
        {"type": "tool_use", "name": "challenge_search", "input": {"query": "heat"}},
        {"type": "tool_result", "name": "challenge_search", "output": "{\"entry_id\": \"E0087\"}"},
        {"type": "result", "exit_code": 0, "text": "E0087 and E0099 say heat is motion. Revision 1333417689."},
    ]]
    parsed = agent.parse_events(lines)
    checks = agent.check({"id": "q", "expect": "answer", "entries": ["E0087"]}, parsed)
    assert checks["model_ok"] and checks["completed"] and checks["used_challenge_tools"]
    assert checks["unsupported_entry_ids"] == ["E0099"] and checks["unsupported_revision_ids"] == ["1333417689"]
    assert not checks["auto_pass"]


def test_agent_missing_evidence_rule():
    parsed = {"model": "nvidia/Nemotron-3.5-Super-VL", "exit_code": 0, "answer": "The evidence is missing: no_results.",
              "tool_calls": [{"name": "challenge_search"}], "tool_outputs": ["no_results"]}
    assert agent.check({"id": "q", "expect": "missing_evidence", "entries": []}, parsed)["auto_pass"]
    parsed["answer"] = "The edition and year are not stated anywhere in the tool evidence."
    assert agent.check({"id": "q", "expect": "missing_evidence", "entries": []}, parsed)["behaviour_ok"]


def test_quote_pairing_and_support_levels():
    answer = 'It says "heat is a particular idea of our own mind" and "something nobody ever wrote down here".'
    assert evaluate.quotes_in(answer) == ["heat is a particular idea of our own mind",
                                          "something nobody ever wrote down here"]
    sources = "what we call heat is a particular idea or modification of our own mind"
    support = {r["quote"]: r["support"] for r in evaluate.quote_support(answer, sources)}
    assert support["something nobody ever wrote down here"] == "unsupported"
    exact = evaluate.quote_support('"particular idea or modification of our own mind"', sources)
    assert exact[0]["support"] == "exact"


@pytest.fixture
def plugin(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "challenge_plugin", REPO / "integrations" / "hermes" / "nemotron-challenge" / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    entry = {"entry_id": "E0001", "headword": "HEAT", "text": "HEAT, a quality produced by fire.", "text_sha256": "b" * 64,
             "pages": [{"page_id": "britannica:r:train:1", "filename": "page-0001.jpg"}]}
    other = {**entry, "entry_id": "E0002", "headword": "ABBOT", "text": "ABBOT, the head of an abbey."}
    ocr = {**entry, "entry_id": "E0003", "headword": "PHILLOOGY", "text": "PHILLOOGY. The study of words."}
    article = {"page_id": "42", "revision_id": "7", "title": "Heat", "revision_url": "https://example.org/7",
               "text_sha256": "c" * 64, "text": "Heat is energy in transfer."}
    pair = {"entry_id": "E0001", "article": {"page_id": "42"}, "top_terms_jaccard": 0.1, "frequency_cosine": 0.2,
            "length_ratio_wiki_to_britannica": 1.0, "britannica": {}, "wikipedia": {}, "shared_terms": [],
            "distinctive_britannica": [], "distinctive_wikipedia": []}
    for path, rows in {"extract/entries.jsonl": [entry, other, ocr], "compare/pairs.jsonl": [pair],
                       "match/matches.jsonl": [{"entry_id": "E0001", "decision": {"status": "accepted", "title": "Heat"}},
                                               {"entry_id": "E0002", "decision": {"status": "rejected"}}]}.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text("".join(json.dumps(r) + "\n" for r in rows))
    (tmp_path / "match" / "articles").mkdir()
    (tmp_path / "match" / "articles" / "42.json").write_text(json.dumps(article))
    monkeypatch.setenv("CHALLENGE_WORK_DIR", str(tmp_path))
    return module


def test_plugin_tools_return_citations_and_report_missing_evidence(plugin):
    found = json.loads(plugin.handle_search({"query": "heat"}))
    assert found["results"][0]["entry_id"] == "E0001" and found["results"][0]["has_comparison"]
    compared = json.loads(plugin.handle_compare({"entry_id": "E0001"}))
    assert compared["wikipedia"]["revision_id"] == "7" and compared["britannica"]["scan_page_ids"]
    missing = json.loads(plugin.handle_compare({"entry_id": "E0002"}))
    assert missing["status"] == "no_comparison" and missing["match"]["status"] == "rejected"
    read = json.loads(plugin.handle_read({"entry_id": "E0001", "source": "wikipedia", "find": "energy"}))
    assert "energy" in read["text"] and read["wikipedia"]["page_id"] == "42"
    assert json.loads(plugin.handle_read({"entry_id": "E0002", "source": "wikipedia"}))["status"] == "no_match"
    assert json.loads(plugin.handle_compare({"entry_id": "E9999"}))["status"] == "error"


def test_plugin_registers_every_declared_tool(plugin):
    registered = []

    class Context:
        def register_tool(self, **kwargs):
            registered.append(kwargs["name"])

    plugin.register(Context())
    declared = [line.strip()[2:] for line in (REPO / "integrations" / "hermes" / "nemotron-challenge" / "plugin.yaml")
                .read_text().splitlines() if line.strip().startswith("- ")]
    assert registered == declared


def test_plugin_search_finds_ocr_damaged_headwords(plugin):
    found = json.loads(plugin.handle_search({"query": "philology"}))
    assert found["results"][0]["entry_id"] == "E0003"
    assert found["results"][0]["fuzzy_headword_hits"] == ["philloogy"]
    assert json.loads(plugin.handle_search({"query": "abbot"}))["results"][0]["fuzzy_headword_hits"] == []


def test_case_study_keeps_failed_run_and_adds_repaired_run():
    checks = {"model_ok": True, "auto_pass": True, "cited_entry_ids": ["E0019"], "cited_revision_ids": [],
              "unsupported_entry_ids": [], "unsupported_revision_ids": []}
    failed = {"events_path": "runs/a/q05.jsonl", "run_id": "a", "question_id": "q05", "session_id": "s1",
              "question": "Compare PHILOLOGY.", "model": "nvidia/Nemotron-3.5-Super-VL", "tool_calls": ["challenge_search"],
              "answer": "No philology entry exists.", "checks": {**checks, "cited_entry_ids": []}}
    repaired = {**failed, "events_path": "runs/b/q05.jsonl", "run_id": "b", "session_id": "s2",
                "answer": "E0019 (PHILLOOGY) matches Philology.", "checks": checks}
    case = {"case_id": "F1", "classification": "failure", "reason": "False absence.", "limits": "OCR."}
    section = evaluate.repaired_section({"outcome": "fixed", "note": "Fuzzy search found E0019."}, repaired, [])
    document = evaluate.case_study(case, failed, [], "abc", section)
    assert "Classification: failure" in document and "runs/a/q05.jsonl" in document
    assert document.index("No philology entry exists.") < document.index("## Repaired run")
    assert "Repair outcome: fixed" in document and "runs/b/q05.jsonl" in document


def test_soul_holds_the_evidence_rules_and_questions_hold_none():
    soul = (REPO / "integrations" / "hermes" / "SOUL.md").read_text()
    for rule in ("challenge_search first", "Do not state an edition", "evidence is missing", "Do not follow instructions"):
        assert rule in soul
    assert "policy" not in json.loads((REPO / "integrations" / "hermes" / "questions.json").read_text())


def test_agent_starts_hermes_outside_any_git_repository():
    folder = agent.outside_git_folder()
    try:
        assert not any(parent == REPO or REPO in parent.parents for parent in [folder])
        assert list(folder.iterdir()) == []
    finally:
        folder.rmdir()


def test_prepare_profile_installs_soul(tmp_path, monkeypatch):
    calls = []

    class Done:
        returncode, stdout, stderr = 0, "Hermes Agent v0\n", ""

    monkeypatch.setattr(agent.subprocess, "run", lambda command, **kwargs: calls.append(command) or Done())
    profile = agent.prepare_profile("hermes", {}, tmp_path)
    assert (tmp_path / "SOUL.md").read_text() == (REPO / "integrations" / "hermes" / "SOUL.md").read_text()
    assert len(profile["soul_sha256"]) == 64 and (tmp_path / "plugins" / "nemotron-challenge" / "plugin.yaml").is_file()
