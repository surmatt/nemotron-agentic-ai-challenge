# Video script

Length: about 3 minutes.
Parts: website demo, facts and results, our solution against the first run.
Sources for each fact: [evidence/facts.json](evidence/facts.json).
Numbers come from the stage summaries in `artifacts/` (run of 2026-10-18, 13:13 to 13:26 UTC).

Each scene lists the screen, the voice-over (VO), and the on-screen text (TEXT).

## Part 1. Website demo (about 60 s)

Open the site first:

```sh
uv run python -m http.server 8791 --bind 127.0.0.1 --directory artifacts/site
```

### 1.1 Overview (`index.html`), 10 s

- Screen: the Coverage table.
- VO: "We took 100 pages of the Encyclopaedia Britannica, from the first edition of 1771 to the eighth edition, and compared them with today's Wikipedia."
- TEXT: "100 scans · 86 Wikipedia matches · 98 LaTeX documents · 45 agent runs"
- The site shows 241 entries and `site/summary.json` lists 249 entry pages. Do not show an entry count until the two agree.
- Source: `artifacts/site/summary.json`, `artifacts/match/summary.json`.

### 1.2 Colours, 5 s

- Screen: zoom on the legend line.
- VO: "Brown is the old Britannica text. Blue is Wikipedia. Grey is what our models wrote."
- TEXT: none.

### 1.3 A scan page (`scans/1805.html`), 15 s

- Screen: the scan image, then scroll to the block table.
- VO: "Each page keeps the original scan. Parse 3.5 reads it. Super VL looks at the same crop and fixes the OCR. You can see both texts side by side."
- TEXT: "Parse 3.5: 'fo reviewing ... fanc-tany' → Super VL: 'for reviving ... sanctuary'"
- Then click "PDF": "Every page also compiles to a LaTeX document."

### 1.4 An entry page (`entries/E0245.html`), 15 s

- Screen: the hedgehog entry, Britannica text, the matched Wikipedia article, the two term lists.
- VO: "For each entry, the Nemotron embedder and reranker find the matching Wikipedia article. Then we count which words each side uses more."
- TEXT: "More in 1771: 'hog', 'muzzle', 'jaw' · More in Wikipedia: 'spines', 'hedgehogs', 'defense'"

### 1.5 Agent runs (`agent.html`), 15 s

- Screen: one run with the question, the tool calls, and the answer.
- VO: "Our Hermes agent answers questions with four tools. It must cite a scan ID or a Wikipedia revision for each claim. When the evidence is missing, it must say so."
- Suggested run: `q07-william` ("Is the match correct?"). The agent checks our own matcher.

## Part 2. Facts and results (about 60 s)

### 2.1 ENERGY, 25 s

- Screen: scan crop of entry E0037 (scan 523, block 9). Highlight "emphasis of speech".
- VO: "In the 1780s, the whole Britannica entry on energy was two lines long."
- TEXT (quote): "ENERGY, a term of Greek origin, signifying the power, virtue, or efficacy of a thing. It is also used, figuratively, to denote emphasis of speech."
- VO: "Energy meant force of speech. In 1802, Thomas Young first used the word in its modern sense. Today it is the base of all physics: energy cannot be created or destroyed."
- TEXT: "Wikipedia, 'History of energy', revision 1315594974"
- Caption rule: say "1780s" or "second edition". The dataset gives no year.

### 2.2 EXERCISE, 25 s

- Screen: scan crop of entry E0163 (scan 1805, blocks 18 and 19). Highlight "riding in a coach".
- VO: "The fourth edition says there are two kinds of exercise. Active: walking, hunting, dancing. And passive: riding in a coach."
- TEXT (quote): "The passive is riding in a coach, on horseback, or in any other manner."
- VO: "A study from 1949 tells a different story. Bus drivers sat all day and had more heart disease. Bus conductors walked all day and had less."
- The Wikipedia source names Jerry Morris and 1949 (reported 1953). It does not name a city.
- TEXT: "Wikipedia, 'Exercise', revision 1348682182"

### 2.3 Blooper: Lake Erie, 10 s

- Screen: three lines, one after the other.
  - Scan: "ERIE, a **vast** lake"
  - Parse 3.5: "ERRI, a **wall take**"
  - Super VL: "ERIE, a **salt** lake"
- VO: "Our OCR corrector once made a fact up. The scan says 'vast lake'. The model wrote 'salt lake'. Lake Erie is fresh water. We found it because we keep the raw scan next to every corrected line."
- Source: `artifacts/correct/raw/crop_nothink/page-2473-b849fb7f25f2-b18.json`.

## Part 3. Our solution against the first run (about 45 s)

The first run is `artifacts/archive/2026-10-18-initial` (11:34 UTC): Parse text only, lexical title rule, no Nemotron retrieval models.

### 3.1 OCR, 10 s

- Screen: two bars.
- TEXT: "Character error rate: 12.2% → 1.8%" · "Word error rate: 25.1% → 3.0%"
- VO: "Super VL cut the OCR errors almost seven times."
- Source: [docs/evaluation/ocr-correction.md](../docs/evaluation/ocr-correction.md), 29 hand-transcribed blocks.

### 3.2 Matching, 15 s

- Screen: three bars, "first candidate is correct".
- TEXT: "BM25 28% · embedder 49% · reranker 65%" and "accepted matches: 57 → 86"
- VO: "The reranker puts the right article first two times out of three. We now accept 86 matches instead of 57."
- Honest line in TEXT: "On 60 hand labels: F1 0.56 → 0.59 (cross-validated)."
- Source: [docs/evaluation/match-calibration.md](../docs/evaluation/match-calibration.md), `artifacts/archive/2026-10-18-initial/match/summary.json`.

### 3.3 Agent, 10 s

- Screen: a before and after card.
- TEXT: "Before: 'the 1911 Encyclopaedia Britannica' (no evidence) → After: no edition stated without tool evidence"
- VO: "Without rules, our agent invented an edition year. With evidence rules, it stopped."
- Source: case F3 in [docs/evaluation/cases.json](../docs/evaluation/cases.json).

### 3.4 What still fails, 10 s

- TEXT: "Our matcher missed EXERCISE: the right article ranked first, but the margin was 0.015 (rule: 0.5)."
- VO: "We show our misses too. Every claim on the site links to a scan or a Wikipedia revision."

## Outro, 5 s

- TEXT: team name, repository link, "Britannica scans: National Library of Scotland, CC0 1.0 · Wikipedia text: CC BY-SA 4.0".

## Remotion build

The scenes are in `video/src/` (composition `MainVideo`, 1920x1080, 30 fps, 2:57.5).
The voice-over lines show as subtitles. Prepare the assets first:

```sh
uv run python video/scripts/prepare_assets.py
```

The outro has two placeholders: `[Team name]` and `[Repository link]`.

## Open points

- ENERGY and EXERCISE are not pipeline pairs. The match stage skipped ENERGY (shorter than 150 characters) and rejected EXERCISE (margin rule). The Wikipedia side came from a manual API search. Do not say in the video that the matcher found them.
- The mean frequency cosine rose from 0.167 to 0.237, but the two runs compare different pairs. Leave it out of the video, or label it.
- The Lake Erie case is not yet in `docs/evaluation/cases.json`.
