# Team pipeline

This file describes the methods that the team chose for each stage.
Each stage module in `src/nemotron_challenge/` explains its method at the top of the file.

## Run all stages

```sh
uv sync --locked
uv run nemotron-challenge data fetch
uv run nemotron-challenge run extract
uv run nemotron-challenge run correct
uv run nemotron-challenge run match
uv run nemotron-challenge run compare
uv run nemotron-challenge run index
uv run nemotron-challenge run agent
uv run nemotron-challenge run site
uv run nemotron-challenge run evaluate
uv run nemotron-challenge stages
```

Each stage writes to `artifacts/<stage>/` and writes `summary.json` last.
Each stage reads the files of the earlier stages.
LanceDB (`CHALLENGE_DB_PATH`, default `data/team.lancedb`) holds the provenance records and the passage vectors.
Each stage replaces its own provenance records, so old runs leave no stale records. Each work dir has its own tables.
After `correct` has run, `match`, `compare`, the agent tools, and `site` use the corrected text.
Failed model calls go to `artifacts/runs/failures.jsonl` with their error details.

The agent stage needs Hermes Agent. Read [hermes.md](hermes.md).
The site stage compiles LaTeX with `tectonic` when it is installed. Without it, the stage writes `.tex` files only.

## Methods

| Stage | Module | Method |
| --- | --- | --- |
| Extract | `extract.py` | Parse 3.5 per scan. Raw replies stay unchanged in `extract/raw/`. Page headers, footers, and page numbers are removed. A capitalised headword starts an entry. Continuations join only across consecutive rows of one volume. |
| Correct | `correct.py`, `ocr_eval.py` | Super 3.5 VL reads an enlarged crop of each Parse block with the Parse text and returns corrected text. Reasoning is off. Raw replies stay unchanged in `correct/raw/`. Parse text stays when the box is too small or the call fails. Gold-set results: [ocr-correction.md](evaluation/ocr-correction.md). |
| Match | `match.py`, `terms.py` | Three to four BM25 searches per entry: headword, an OCR headword variant, headword plus the top 6 frequency words of the whole entry text and headers (long-s repaired, dictionary-filtered), and the Super VL title guess with its terms. Super VL reads the entry text, the page text, and the page image; raw replies stay in `match/terms/`. With the retrieval service: accept the reranker's first candidate when its logit, embedder cosine, and title similarity pass the thresholds. The gap to the second candidate does not affect acceptance ([match-calibration.md](evaluation/match-calibration.md)). Without it: a headword and title rule, labelled `provisional_lexical`. |
| Compare | `compare.py` | Word frequencies. Long s and historical spelling are normalised and logged. Log-odds z-scores with an informative Dirichlet prior. Each distinctive term has one source snippet per side. |
| Index | `index.py`, `search.py`, `storage.py` | Splits Britannica entries and accepted Wikipedia articles into passages of about 1,200 characters, embeds them with Embed VL, and writes them with their citations to LanceDB (`britannica_passages`, `wikipedia_passages`). Stored vectors are reused. Search: `uv run python -m nemotron_challenge.search --query "..."`. |
| Agent | `agent.py`, `integrations/hermes/` | Hermes with Super 3.5 VL and five tools: search, semantic search (LanceDB), compare, read, corpus. The evidence rules are in `integrations/hermes/SOUL.md`; the questions are in `integrations/hermes/questions.json`. |
| Site | `site.py` | Static HTML and one LaTeX document per scan. Source text and generated analysis have separate, labelled sections. |
| Evaluate | `evaluate.py`, `evaluation/cases.json` | The team classifies six saved runs by hand. The stage checks quotes against the tool results and writes the case studies. |

## Open the site

```sh
uv run python -m http.server 8791 --bind 127.0.0.1 --directory artifacts/site
```

Open `http://127.0.0.1:8791/` in a browser.

## Known limits

- The first full runs used the lexical match rule, before the embedder and reranker were deployed.
- The first model run used `RERANK_ACCEPT = 0.0` and `COSINE_ACCEPT = 0.30` and accepted 1 of 188 entries.
  Its output is in `artifacts/runs/match-run1-uncalibrated/`.
- The model rule reads its thresholds from `docs/evaluation/match_thresholds.json` (logit, cosine, title similarity).
  Legacy margin values are ignored. Saved decisions still use their original rule until Match runs again.
  Without that file, it accepts the reranker top-1 if its logit is at least -6.0 and its title similarity is at least 0.75.
- Recalibrate after a change to the candidates or the entry text. First save the candidate set the labeller saw: `uv run python -c "from pathlib import Path; from nemotron_challenge.calibrate import snapshot_judged; snapshot_judged(Path('artifacts'))"`. Then run match again and fit the new thresholds: `uv run python -c "from pathlib import Path; from nemotron_challenge.calibrate import run; run(Path('artifacts'))"`.
- `artifacts/evaluate/summary.json` lists the other known limits.
