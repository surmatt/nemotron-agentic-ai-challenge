"""Agent stage: run the team's question set through Hermes with Super 3.5 VL and the challenge tools.

Method (team choice):
1. Prepare a separate Hermes profile in data/hermes: config from integrations/hermes, the current plugin,
   and integrations/hermes/SOUL.md. SOUL.md holds the evidence rules, so they also apply in `hermes chat`.
2. Run each question with `hermes chat --oneshot --format stream-json`, limited to the challenge toolset.
   Hermes starts in an empty temporary folder outside this repository. Inside a git repository Hermes
   loads the AGENTS.md chain from the git root, and this repository's AGENTS.md is a coding guide.
   `--ignore-rules` is not used, because it also turns off SOUL.md.
3. Save every event stream unchanged. Never replace a failed run with an invented answer.
4. Check each run: expected model ID, completed result, challenge tool calls, and whether each entry ID
   and Wikipedia revision ID in the answer occurs in a tool result. The expected behaviour per question
   (answer, missing evidence, wrong match) is checked with simple text rules and then reviewed by hand
   in the evaluate stage.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from dotenv import dotenv_values

from .common import text_dir, read_jsonl, append_jsonl, read_json, sha256_text, utc_now, write_json, write_text
from .config import SUPER_MODEL, Settings

REPO = Path(__file__).resolve().parents[2]
HERMES_SOURCE = REPO / "integrations" / "hermes"
RUN_TIMEOUT = 420
MISSING_WORDS = re.compile(r"no (?:accepted )?(?:match|comparison|evidence|results?|entry)|not found|missing|"
                           r"does not (?:exist|contain|have)|no wikipedia|unavailable|cannot (?:compare|find)|"
                           r"not (?:stated|provided|given)", re.I)
WRONG_MATCH_WORDS = re.compile(r"(?:wrong|incorrect|mismatch|not the same|different (?:subject|place|topic)|"
                               r"does not (?:match|describe|correspond)|unrelated|mis-?match)", re.I)


def hermes_binary() -> str:
    found = shutil.which("hermes") or str(Path.home() / ".local" / "bin" / "hermes")
    if not Path(found).is_file():
        raise FileNotFoundError("Hermes is not installed. Read docs/hermes.md.")
    return found


def hermes_env(settings: Settings, home: Path, work_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update({k: v for k, v in dotenv_values(REPO / ".env").items() if v is not None and k not in env})
    if not settings.super_api_key:
        raise ValueError("SUPER_API_KEY is missing in .env")
    env.update({"HERMES_HOME": str(home), "CHALLENGE_WORK_DIR": str(work_dir.resolve()),
                "SUPER_API_KEY": settings.super_api_key,
                # The semantic search tool runs the project Python, which has LanceDB and the clients.
                "CHALLENGE_PYTHON": sys.executable, "CHALLENGE_REPO": str(REPO)})
    return env


def prepare_profile(hermes: str, env: dict[str, str], home: Path) -> dict[str, Any]:
    """Copy the config once, and the current plugin and SOUL.md every run. Check the plugin with Plugin Doctor."""
    (home / "plugins").mkdir(parents=True, exist_ok=True)
    if not (home / "config.yaml").is_file():
        shutil.copy(HERMES_SOURCE / "config.example.yaml", home / "config.yaml")
    soul = (HERMES_SOURCE / "SOUL.md").read_text(encoding="utf-8")
    write_text(home / "SOUL.md", soul)
    target = home / "plugins" / "nemotron-challenge"
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(HERMES_SOURCE / "nemotron-challenge", target,
                    ignore=shutil.ignore_patterns("__pycache__"))
    doctor = subprocess.run([hermes, "plugins", "doctor", str(HERMES_SOURCE / "nemotron-challenge"), "--ci"],
                            env=env, capture_output=True, text=True, timeout=180)
    subprocess.run([hermes, "plugins", "enable", "nemotron-challenge"], env=env, capture_output=True, text=True,
                   timeout=60)
    version = subprocess.run([hermes, "--version"], env=env, capture_output=True, text=True, timeout=60)
    if doctor.returncode != 0:
        raise ValueError(f"Hermes Plugin Doctor failed: {doctor.stdout[-400:]} {doctor.stderr[-400:]}")
    return {"plugin_doctor": "ok", "hermes_version": version.stdout.strip().splitlines()[0] if version.stdout else "",
            "soul_sha256": sha256_text(soul)}


def outside_git_folder() -> Path:
    """An empty folder outside every git repository, so Hermes loads no project context file."""
    folder = Path(tempfile.mkdtemp(prefix="hermes-challenge-"))
    inside = subprocess.run(["git", "-C", str(folder), "rev-parse", "--is-inside-work-tree"],
                            capture_output=True, text=True)
    if inside.returncode == 0:
        raise ValueError(f"temporary folder {folder} is inside a git repository")
    return folder


def parse_events(lines: list[str]) -> dict[str, Any]:
    events, bad = [], 0
    for line in lines:
        try:
            events.append(json.loads(line))
        except ValueError:
            bad += 1
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    calls = [{"name": e.get("name"), "input": e.get("input")} for e in events if e.get("type") == "tool_use"]
    outputs = [str(e.get("output", "")) for e in events if e.get("type") == "tool_result"]
    return {"events": len(events), "invalid_lines": bad, "model": init.get("model"),
            "session_id": init.get("session_id") or result.get("session_id"), "exit_code": result.get("exit_code"),
            "answer": result.get("text", ""), "tool_calls": calls, "tool_outputs": outputs}


def check(question: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    answer, outputs = parsed["answer"], "\n".join(parsed["tool_outputs"])
    entry_ids = sorted(set(re.findall(r"\bE[0-9]{4}\b", answer)))
    revisions = sorted(set(re.findall(r"\b1[0-9]{9}\b", answer)))
    checks = {
        "model_ok": parsed["model"] == SUPER_MODEL,
        "completed": parsed["exit_code"] == 0 and bool(answer.strip()),
        "used_challenge_tools": any((c["name"] or "").startswith("challenge_") for c in parsed["tool_calls"]),
        "cited_entry_ids": entry_ids,
        "unsupported_entry_ids": [e for e in entry_ids if e not in outputs],
        "cited_revision_ids": revisions,
        "unsupported_revision_ids": [r for r in revisions if r not in outputs],
        "expected_entries_found": all(e in outputs for e in question.get("entries", [])),
    }
    expect = question["expect"]
    if expect == "answer":
        checks["behaviour_ok"] = bool(entry_ids or question["id"].endswith("corpus")) and not checks["unsupported_entry_ids"]
    elif expect == "missing_evidence":
        checks["behaviour_ok"] = bool(MISSING_WORDS.search(answer)) and not revisions
    else:
        checks["behaviour_ok"] = bool(WRONG_MATCH_WORDS.search(answer))
    checks["auto_pass"] = all([checks["model_ok"], checks["completed"], checks["used_challenge_tools"],
                               not checks["unsupported_entry_ids"], not checks["unsupported_revision_ids"],
                               checks["behaviour_ok"]])
    return checks


def resolve_entries(question: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Find the question's entry IDs from its headwords. IDs are sequential and shift between runs."""
    if not question.get("headwords"):
        return question
    ids = [e["entry_id"] for e in entries if e["headword"] in question["headwords"]]
    return {**question, "entries": ids, "entries_resolved_from": question["headwords"]}


def run(settings: Settings, work_dir: Path, only: list[str] | None = None) -> dict[str, Any]:
    for needed in (f"{text_dir(work_dir).name}/entries.jsonl", "match/matches.jsonl", "compare/pairs.jsonl"):
        if not (work_dir / needed).is_file():
            raise FileNotFoundError(f"{work_dir / needed} is missing. Run the earlier stages first.")
    hermes, home = hermes_binary(), REPO / "data" / "hermes"
    env = hermes_env(settings, home, work_dir)
    profile = prepare_profile(hermes, env, home)
    spec = read_json(HERMES_SOURCE / "questions.json")
    run_id = utc_now().replace(":", "").replace("+0000", "Z")
    out = work_dir / "agent"
    run_dir = out / "runs" / run_id
    sandbox = outside_git_folder()
    rows = []
    entries = read_jsonl(text_dir(work_dir) / "entries.jsonl")
    for question in spec["questions"]:
        if only and question["id"] not in only:
            continue
        question = resolve_entries(question, entries)
        started = utc_now()
        command = [hermes, "chat", "-q", question["question"], "--oneshot",
                   "--format", "stream-json", "-t", "nemotron_challenge",
                   "--max-turns", "12", "--run-budget", str(RUN_TIMEOUT - 60)]
        try:
            done = subprocess.run(command, env=env, cwd=sandbox, capture_output=True, text=True, timeout=RUN_TIMEOUT)
            stdout, stderr, code = done.stdout, done.stderr, done.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr, code = f"timeout after {RUN_TIMEOUT} s", None
        write_text(run_dir / f"{question['id']}.jsonl", stdout)
        write_text(run_dir / f"{question['id']}.stderr.txt", stderr)
        parsed = parse_events([line for line in stdout.splitlines() if line.strip()])
        checks = check(question, parsed)
        row = {"run_id": run_id, "question_id": question["id"], "question": question["question"],
               "expect": question["expect"], "entries": question.get("entries", []), "started_at": started,
               "finished_at": utc_now(),
               "process_exit_code": code, "events_path": str(run_dir / f"{question['id']}.jsonl"),
               "model": parsed["model"], "session_id": parsed["session_id"],
               "tool_calls": [c["name"] for c in parsed["tool_calls"]], "answer": parsed["answer"], "checks": checks,
               "soul_sha256": profile["soul_sha256"]}
        if not checks["completed"]:
            append_jsonl(work_dir / "runs" / "failures.jsonl", {
                "stage": "agent", "run_id": run_id, "question_id": question["id"], "process_exit_code": code,
                "error": stderr[-600:], "at": utc_now()})
        append_jsonl(out / "runs.jsonl", row)
        rows.append(row)
    summary = {
        "stage": "agent", "finished_at": utc_now(), "run_id": run_id, "model": SUPER_MODEL, **profile,
        "questions": len(rows), "completed": sum(r["checks"]["completed"] for r in rows),
        "auto_pass": sum(r["checks"]["auto_pass"] for r in rows),
        "results": {r["question_id"]: {"auto_pass": r["checks"]["auto_pass"], "tools": len(r["tool_calls"])}
                    for r in rows},
        "outputs": {"runs": str(out / "runs.jsonl"), "events": str(run_dir)},
        "note": "Automatic checks are text rules. Read each answer before you classify it.",
    }
    write_json(out / "summary.json", summary)
    shutil.rmtree(sandbox, ignore_errors=True)
    return summary
