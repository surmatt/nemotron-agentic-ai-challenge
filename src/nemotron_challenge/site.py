"""Site stage: compile one LaTeX document per scan and build a static website that links all evidence.

Layout (team choice):
- index.html: coverage, stage summaries, corpus plots, and links.
- scans/<row>.html: the scan image, the extracted blocks, the entries on the page, the PDF, and the raw reply.
- entries/<id>.html: Britannica source text, the match decision, the Wikipedia source excerpt, and the
  generated comparison. Each kind of content sits in its own labelled section.
- agent.html: every saved agent run with its automatic checks.
The site uses only static files, so any web server or file browser can open it.
"""
from __future__ import annotations

from collections import defaultdict
import html
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

from .common import text_dir, read_json, read_jsonl, sha256_text, utc_now, write_json, write_text
from .config import Settings
from .data import load_manifest

REPO = Path(__file__).resolve().parents[2]
CSS = """
body{font-family:Georgia,serif;max-width:980px;margin:0 auto;padding:16px;color:#222;background:#fff;line-height:1.5}
nav a{margin-right:12px} h1,h2,h3{font-family:Helvetica,Arial,sans-serif} table{border-collapse:collapse;width:100%}
td,th{border:1px solid #ccc;padding:4px 6px;font-size:14px;vertical-align:top;text-align:left}
.source{border-left:6px solid #8a5a2b;background:#fbf7f1;padding:8px 12px;white-space:pre-wrap;font-size:14px}
.wiki{border-left:6px solid #2b5a8a;background:#f1f6fb;padding:8px 12px;white-space:pre-wrap;font-size:14px}
.generated{border-left:6px solid #666;background:#f4f4f4;padding:8px 12px}
.label{font:bold 12px Helvetica,Arial,sans-serif;text-transform:uppercase;color:#555;margin-top:16px}
.ok{color:#176b2c}.bad{color:#a11}.muted{color:#666;font-size:13px} img.scan{max-width:100%;border:1px solid #ccc}
code{font-size:12px;word-break:break-all}
"""
LATEX_SPECIAL = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&", "#": r"\#",
                 "^": r"\textasciicircum{}", "_": r"\_", "%": r"\%", "~": r"\textasciitilde{}"}


def esc(text: Any) -> str:
    return html.escape(str(text if text is not None else ""))


def tex(text: str) -> str:
    text = "".join(ch for ch in text if ch in "\n\t" or ord(ch) >= 32)
    return "".join(LATEX_SPECIAL.get(ch, ch) for ch in text)


def page(title: str, body: str, depth: int = 0) -> str:
    up = "../" * depth
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{esc(title)}</title>"
            f"<link rel=\"stylesheet\" href=\"{up}style.css\"></head><body><nav><a href=\"{up}index.html\">Overview</a>"
            f"<a href=\"{up}scans.html\">Scans</a><a href=\"{up}entries.html\">Entries</a>"
            f"<a href=\"{up}agent.html\">Agent runs</a></nav><h1>{esc(title)}</h1>{body}"
            f"<p class=\"muted\">Britannica scans: National Library of Scotland, CC0 1.0. Wikipedia text: Wikipedia "
            f"contributors, CC BY-SA 4.0, revision links on each page. Generated {esc(utc_now())}.</p></body></html>")


def text_note(scan: dict[str, Any]) -> str:
    sources = {b.get("text_source", "parse") for b in scan["blocks"]}
    if "super_vl" in sources:
        return ("Parse 3.5 extracted the text. Super 3.5 VL corrected it from an enlarged crop of each block. "
                "It can still contain recognition errors.")
    return "The text below is Parse 3.5 OCR output. It contains recognition errors."


def correction_item(scan: dict[str, Any]) -> str:
    counts: dict[str, int] = {}
    for block in scan["blocks"]:
        counts[block.get("text_source", "parse")] = counts.get(block.get("text_source", "parse"), 0) + 1
    if "super_vl" not in counts:
        return ""
    stem = Path(scan["filename"]).stem
    return (f"\\item[Correction] model \\texttt{{nvidia/Nemotron-3.5-Super-VL}}, block crops, raw replies "
            f"\\texttt{{correct/raw/crop\\_nothink/{tex(stem)}-b*.json}}; "
            + ", ".join(f"{tex(k)}: {v}" for k, v in sorted(counts.items())))


def latex_document(scan: dict[str, Any], entries: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    """Fill the structure of templates/page.tex with the extracted entries of one scan."""
    parts = []
    for entry in entries:
        blocks = [p for p in entry["parts"] if p["page_id"] == scan["page_id"]]
        heading = entry["headword"] or "Untitled continuation"
        parts.append(f"\\subsection*{{{tex(heading)} ({entry['entry_id']})}}\n")
        if entry["start_kind"] == "continuation":
            parts.append("\\textit{Continues an entry from an earlier page.}\n\n")
        parts.extend(tex(b["text"]) + "\n\n" for b in blocks)
    body = "".join(parts) or "No entry text was extracted from this scan.\n"
    return f"""\\documentclass{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage[margin=2cm]{{geometry}}
\\usepackage{{hyperref}}
\\sloppy
\\begin{{document}}
\\section*{{Historical source}}
Encyclopaedia Britannica scan, source row {scan['row_index']}. {text_note(scan)}
Page headers, footers, and page numbers are removed.

{body}
\\section*{{Source record}}
\\begin{{description}}
\\item[Scan ID] \\texttt{{{tex(scan['page_id'])}}}
\\item[Image file] \\texttt{{{tex(scan['filename'])}}}
\\item[Image SHA-256] \\texttt{{{scan['image_sha256']}}}
\\item[Dataset] {tex(manifest['dataset'])} at revision \\texttt{{{manifest['revision']}}} ({tex(manifest['license']['spdx'])})
\\item[Extraction] model \\texttt{{nvidia/nemotron-3.5-parse}}, raw reply \\texttt{{{tex(scan['raw_path'])}}}
\\item[Raw reply SHA-256] \\texttt{{{scan['raw_content_sha256']}}}
{correction_item(scan)}
\\item[Running header] {tex(scan['running_header'] or 'none')}
\\end{{description}}
\\end{{document}}
"""


def compile_latex(tex_dir: Path) -> dict[str, Any]:
    engine = shutil.which("tectonic") or next(
        (str(p) for p in [Path.home() / ".local" / "bin" / "tectonic"] if p.is_file()), None)
    if engine is None:
        return {"engine": None, "compiled": 0, "failed": [], "note": "tectonic is not installed; .tex files only"}
    compiled, failed = 0, []
    for source in sorted(tex_dir.glob("*.tex")):
        pdf = source.with_suffix(".pdf")
        if pdf.is_file() and pdf.stat().st_mtime >= source.stat().st_mtime:
            compiled += 1
            continue
        done = subprocess.run([engine, "--chatter", "minimal", str(source.name)], cwd=tex_dir,
                              capture_output=True, text=True, timeout=300)
        if done.returncode == 0 and pdf.is_file():
            compiled += 1
        else:
            failed.append({"file": source.name, "error": (done.stderr or done.stdout)[-500:]})
    version = subprocess.run([engine, "--version"], capture_output=True, text=True).stdout.strip()
    return {"engine": version, "compiled": compiled, "failed": failed}


def terms_table(rows: list[dict[str, Any]], side: str) -> str:
    out = ["<table><tr><th>Term</th><th>z</th><th>Britannica</th><th>Wikipedia</th><th>Evidence</th></tr>"]
    for row in rows[:10]:
        snip = row.get(f"{side}_snippet") or {}
        out.append(f"<tr><td>{esc(row['term'])}</td><td>{row['z']}</td><td>{row['count_britannica']}</td>"
                   f"<td>{row['count_wikipedia']}</td><td class=\"muted\">{esc(snip.get('text', ''))}</td></tr>")
    return "".join(out) + "</table>"


def run(settings: Settings, work_dir: Path, raw_scans: Path = Path("data/raw/britannica")) -> dict[str, Any]:
    del settings
    manifest = load_manifest()
    source = text_dir(work_dir)
    scans = read_jsonl(source / "pages.jsonl")
    entries = read_jsonl(source / "entries.jsonl")
    matches = {m["entry_id"]: m for m in read_jsonl(work_dir / "match" / "matches.jsonl")}
    pairs = {p["entry_id"]: p for p in read_jsonl(work_dir / "compare" / "pairs.jsonl")}
    summaries = {s: read_json(work_dir / s / "summary.json") for s in ("extract", "match", "compare")}
    agent_rows = read_jsonl(work_dir / "agent" / "runs.jsonl") if (work_dir / "agent" / "runs.jsonl").is_file() else []
    site = work_dir / "site"
    write_text(site / "style.css", CSS)

    # Scan images and raw replies are copied so the site works without the repository.
    by_page: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        for p in entry["pages"]:
            by_page[p["page_id"]].append(entry)
    tex_dir = site / "latex"
    for scan in scans:
        stem = Path(scan["filename"]).stem
        (site / "img").mkdir(parents=True, exist_ok=True)
        shutil.copy(raw_scans / scan["filename"], site / "img" / scan["filename"])
        (site / "raw").mkdir(parents=True, exist_ok=True)
        shutil.copy(work_dir / scan["raw_path"], site / "raw" / f"{stem}.json")
        document = latex_document(scan, by_page[scan["page_id"]], manifest)
        target = tex_dir / f"{stem}.tex"
        if not target.is_file() or target.read_text(encoding="utf-8") != document:
            write_text(target, document)
    latex = compile_latex(tex_dir)

    failed_ids = set(summaries["extract"]["failed_scans"])
    scan_rows = []
    for item in manifest["pages"]:
        scan = next((s for s in scans if s["page_id"] == item["page_id"]), None)
        stem = Path(item["filename"]).stem
        if scan is None:
            scan_rows.append(f"<tr><td>{item['row_index']}</td><td class=\"bad\">parse failed</td>"
                             f"<td colspan=\"3\">{esc(summaries['extract']['failure_details'].get(item['page_id'], ''))}"
                             f"</td></tr>")
            continue
        here = by_page[scan["page_id"]]
        links = " ".join(f"<a href=\"../entries/{e['entry_id']}.html\">{esc(e['headword'] or e['entry_id'])}</a>"
                         for e in here)
        pdf = (f"<a href=\"../latex/{stem}.pdf\">PDF</a>" if (tex_dir / f"{stem}.pdf").is_file()
               else "PDF not compiled")
        blocks = "".join(
            f"<tr><td>{b['index']}</td><td>{esc(b['cls'])}</td><td class=\"muted\">{b['bbox']}</td>"
            f"<td class=\"muted\">{esc(b.get('parse_text', b['text'])[:600])}</td><td>{esc(b['text'][:600])}</td>"
            f"<td class=\"muted\">{esc(b.get('text_source', 'parse'))}"
            f"{(' · ' + esc(b['review_flag'])) if b.get('review_flag') else ''}</td></tr>" for b in scan["blocks"])
        furniture = ", ".join(f"{esc(b['cls'])}: {esc(b['text'])}" for b in scan["furniture"]) or "none"
        body = (f"<p>Scan ID <code>{esc(scan['page_id'])}</code><br>Image SHA-256 <code>{scan['image_sha256']}</code><br>"
                f"Status: {esc(scan['status'])}. Running header: {esc(scan['running_header'] or 'none')} "
                f"({esc(scan['header_kind'])}). Removed page furniture: {furniture}.</p>"
                f"<p>{pdf} · <a href=\"../raw/{stem}.json\">raw Parse reply</a> · <a href=\"../latex/{stem}.tex\">LaTeX</a>"
                f"</p><p>Entries: {links or 'none'}</p>"
                f"<img class=\"scan\" src=\"../img/{esc(scan['filename'])}\" alt=\"Scan {scan['row_index']}\">"
                f"<div class=\"label\">Extracted blocks (source order): Parse 3.5 text and the text used</div>"
                f"<table><tr><th>#</th><th>Class</th><th>Box</th><th>Parse 3.5</th><th>Used text</th><th>Source</th></tr>"
                f"{blocks}</table>")
        write_text(site / "scans" / f"{scan['row_index']}.html", page(f"Scan {scan['row_index']}", body, 1))
        scan_rows.append(f"<tr><td><a href=\"scans/{scan['row_index']}.html\">{scan['row_index']}</a></td>"
                         f"<td>{esc(scan['status'])}</td><td>{esc(scan['running_header'])}</td><td>{len(here)}</td>"
                         f"<td>{pdf.replace('../', '')}</td></tr>")
    write_text(site / "scans.html", page("Scans", "<table><tr><th>Row</th><th>Status</th><th>Header</th>"
                                          "<th>Entries</th><th>Document</th></tr>" + "".join(scan_rows) + "</table>"))

    entry_rows = []
    for entry in entries:
        match, pair = matches.get(entry["entry_id"]), pairs.get(entry["entry_id"])
        decision = (match or {}).get("decision", {"status": "not searched"})
        scans_links = " ".join(f"<a href=\"../scans/{p['row_index']}.html\">scan {p['row_index']}</a>"
                               for p in entry["pages"])
        body = [f"<p>{scans_links}. Text SHA-256 <code>{entry['text_sha256']}</code>. Start: {esc(entry['start_kind'])}"
                f"{' (joined across pages)' if len(entry['pages']) > 1 else ''}.</p>",
                f"<div class=\"label\">Source text: Britannica, {'Parse 3.5 OCR corrected by Super 3.5 VL' if source.name == 'correct' else 'Parse 3.5 OCR'}</div>",
                f"<div class=\"source\">{esc(entry['text'])}</div>",
                "<div class=\"label\">Generated: match decision</div>",
                f"<div class=\"generated\"><pre>{esc(json.dumps(decision, indent=1))}</pre>"
                f"<p class=\"muted\">Queries: {esc('; '.join((match or {}).get('queries', [])))}</p></div>"]
        if pair:
            article = read_json(work_dir / "match" / "articles" / f"{pair['article']['page_id']}.json")
            body += [f"<div class=\"label\">Source text: Wikipedia, {esc(article['title'])}, revision "
                     f"<a href=\"{esc(article['revision_url'])}\">{article['revision_id']}</a> (first 3,000 of "
                     f"{article['chars']} characters)</div>",
                     f"<div class=\"wiki\">{esc(article['text'][:3000])}</div>",
                     "<div class=\"label\">Generated: word-frequency comparison</div>",
                     f"<div class=\"generated\"><p>Top-terms Jaccard {pair['top_terms_jaccard']}, frequency cosine "
                     f"{pair['frequency_cosine']}, Wikipedia/Britannica length {pair['length_ratio_wiki_to_britannica']}, "
                     f"unverified Britannica tokens {pair['britannica']['unverified_rate']}.</p>"
                     f"<h3>More frequent in Britannica</h3>{terms_table(pair['distinctive_britannica'], 'britannica')}"
                     f"<h3>More frequent in Wikipedia</h3>{terms_table(pair['distinctive_wikipedia'], 'wikipedia')}</div>"]
        title = f"{entry['entry_id']}: {entry['headword'] or 'untitled continuation'}"
        write_text(site / "entries" / f"{entry['entry_id']}.html", page(title, "".join(body), 1))
        cls = "ok" if decision.get("status") == "accepted" else "muted"
        entry_rows.append(f"<tr><td><a href=\"entries/{entry['entry_id']}.html\">{entry['entry_id']}</a></td>"
                          f"<td>{esc(entry['headword'] or '')}</td><td>{entry['chars']}</td>"
                          f"<td class=\"{cls}\">{esc(decision.get('status'))}</td><td>{esc(decision.get('title', ''))}"
                          f"</td><td>{esc(decision.get('method', ''))}</td></tr>")
    write_text(site / "entries.html", page("Entries", "<table><tr><th>ID</th><th>Headword</th><th>Chars</th>"
                                            "<th>Match</th><th>Wikipedia</th><th>Method</th></tr>"
                                            + "".join(entry_rows) + "</table>"))

    runs = []
    for row in reversed(agent_rows):
        checks = row["checks"]
        cls = "ok" if checks["auto_pass"] else "bad"
        runs.append(f"<h2 id=\"{esc(row['run_id'])}-{esc(row['question_id'])}\">{esc(row['question_id'])} "
                    f"<span class=\"muted\">run {esc(row['run_id'])}</span></h2><p>{esc(row['question'])}</p>"
                    f"<p>Model {esc(row['model'])}. Tools: {esc(', '.join(row['tool_calls']))}. "
                    f"Automatic check: <span class=\"{cls}\">{'pass' if checks['auto_pass'] else 'fail'}</span>.</p>"
                    f"<div class=\"label\">Generated: agent answer</div><div class=\"generated\" "
                    f"style=\"white-space:pre-wrap\">{esc(row['answer'] or '(no answer)')}</div>"
                    f"<pre class=\"muted\">{esc(json.dumps(checks, indent=1))}</pre>")
    write_text(site / "agent.html", page("Agent runs", "".join(runs) or "<p>No agent runs yet.</p>"))

    for plot in (work_dir / "compare" / "plots").glob("*.svg"):
        (site / "plots").mkdir(parents=True, exist_ok=True)
        shutil.copy(plot, site / "plots" / plot.name)
    ext, mat, com = summaries["extract"], summaries["match"], summaries["compare"]
    overview = f"""
<p>This site compares 100 historical Encyclopaedia Britannica scans with Wikipedia. Brown sections show
Britannica source text, blue sections show Wikipedia source text, and grey sections show generated analysis.</p>
<h2>Coverage</h2><table>
<tr><td>Scans</td><td>{ext['scans']} ({ext['parsed']} parsed; {len(failed_ids)} Parse failures; status {esc(ext['page_status'])})</td></tr>
<tr><td>Entries</td><td>{ext['entries']} ({ext['headword_entries']} with a headword, {ext['continuation_entries']} continuations,
{ext['joined_across_pages']} joined across pages)</td></tr>
<tr><td>Match</td><td>mode {esc(mat['mode'])}: {mat['searched']} searched, {mat['accepted']} accepted,
{mat['rejected']} rejected, {mat['skipped']} skipped, {mat['errors']} errors. {esc(mat['mode_detail'])}</td></tr>
<tr><td>Compare</td><td>{com['pairs']} pairs; mean top-terms Jaccard {com['mean_top_terms_jaccard']};
mean frequency cosine {com['mean_frequency_cosine']}; unverified Britannica tokens {com['britannica_unverified_rate']}</td></tr>
<tr><td>LaTeX</td><td>{latex['compiled']} of {len(scans)} documents compiled ({esc(latex['engine'] or latex.get('note'))})</td></tr>
<tr><td>Agent</td><td>{len(agent_rows)} saved runs</td></tr></table>
<h2>Vocabulary across matched pairs</h2>
<p><img src="plots/distinctive-britannica.svg" alt="Terms more frequent in Britannica" style="max-width:100%"></p>
<p><img src="plots/distinctive-wikipedia.svg" alt="Terms more frequent in Wikipedia" style="max-width:100%"></p>
<p class="muted">Matches with method "provisional_lexical" come from headword and title rules without the
Nemotron embedder and reranker. They need the model check.</p>"""
    write_text(site / "index.html", page("Britannica and Wikipedia", overview))
    summary = {"stage": "site", "finished_at": utc_now(), "site": str(site / "index.html"),
               "scan_pages": len(scans), "entry_pages": len(entries), "agent_runs": len(agent_rows), "latex": latex,
               "index_sha256": sha256_text((site / "index.html").read_text(encoding="utf-8"))}
    write_json(work_dir / "site" / "summary.json", summary)
    return summary
