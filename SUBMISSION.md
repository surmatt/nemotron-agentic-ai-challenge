# Submission

Team: Surmatotron
Repository URL and commit: <https://github.com/surmatt/nemotron-agentic-ai-challenge>, commit [`ed22b37`](https://github.com/surmatt/nemotron-agentic-ai-challenge/tree/ed22b37cc4d3fbb8f39710b7de6c97d03b3637b5) on `main`
Video URL, 3 to 5 minutes: TODO, the video is in production (script: [video/script.md](video/script.md))
Static website URL: <https://port8790-bmwqhj74ax00h6q.tunnel.applications.uk-south2.nebius.cloud/site/index.html>. The same site is in the repository at [artifacts/site/index.html](artifacts/site/index.html).
The hosted site is built from the end-to-end rerun in `artifacts-e2e3/` (13:52 UTC: 248 entry pages, 8 agent runs). The numbers below come from `artifacts/` (249 entries, 45 agent runs).
Live workbench: <https://port8790-bmwqhj74ax00h6q.tunnel.applications.uk-south2.nebius.cloud/> (Nebius CPU endpoint, open access)
Compiled LaTeX documents: 98 PDFs with their `.tex` sources in [artifacts/site/latex/](artifacts/site/latex/), compiled with Tectonic 0.17.0, no failures

## Reproduce the run

Setup:

```sh
uv sync --locked
cp .env.example .env
uv run nemotron-challenge doctor --offline
uv run nemotron-challenge data fetch
uv run nemotron-challenge doctor --live
```

Set the service URLs and your own keys in `.env`.
Deploy the embedder and reranker as described in [docs/model-service.md](docs/model-service.md).
Install Hermes as described in [docs/hermes.md](docs/hermes.md).

Run the stages in this order:

```sh
uv run nemotron-challenge run extract
uv run nemotron-challenge run correct
uv run nemotron-challenge run match
uv run nemotron-challenge run compare
uv run nemotron-challenge run index
uv run nemotron-challenge run agent
uv run nemotron-challenge run site
uv run nemotron-challenge run evaluate
uv run pytest
```

[docs/team-pipeline.md](docs/team-pipeline.md) describes the method of each stage.

Tested versions:

| Item | Version |
| --- | --- |
| Python | 3.12.0 |
| uv | 0.12.5 |
| httpx | 0.28.1 |
| pydantic | 2.14.1 |
| python-dotenv | 1.2.4 |
| lancedb | 0.40.0 |
| pyarrow | 21.0.0 |
| huggingface-hub | 2.2.0 |
| pillow | 11.1.0 |
| pytest | 9.1.1 (140 tests pass) |
| Hermes Agent | v0.22.2 (2026.9.24), SOUL sha256 `566b9455303da7cf8f8efc4d3b427566e0d7235f03c020ea91bb4a4f8813a4cc` |
| Tectonic | 0.17.0 |

`uv.lock` pins all other packages.

Models and serving settings:

| Stage | Model ID | Revision | Settings |
| --- | --- | --- | --- |
| extract | `nvidia/nemotron-3.5-parse` | organizer service | temperature 0, `max_tokens` 8744 |
| correct | `nvidia/Nemotron-3.5-Super-VL` | Nebius Token Factory | block crop and Parse text, reasoning off, temperature 0, `max_tokens` 3000 |
| match | `nvidia/llama-nemotron-embed-vl-1b-v2` | `582e3bf72aee355e3c59ed89de53543c5b0657ee` | team GPU service, 2048 dimensions |
| match | `nvidia/llama-nemotron-rerank-vl-1b-v2` | `b8a9987b05b75db5ad949c825cbcbf6eb7c48b5a` | team GPU service |
| index | `nvidia/llama-nemotron-embed-vl-1b-v2` | `582e3bf72aee355e3c59ed89de53543c5b0657ee` | LanceDB at `data/team.lancedb` |
| agent | `nvidia/Nemotron-3.5-Super-VL` | Nebius Token Factory | Hermes with five team tools |

The retrieval service uses the recipe in [docs/model-service.md](docs/model-service.md): Python 3.11, PyTorch 2.8.0, CUDA 12.8, Transformers 4.56.2.
The match accept rule is: reranker first candidate, margin of at least 0.5 to the second candidate, cosine of at least 0.15, reranker logit of at least -10.
The thresholds are in [docs/evaluation/match_thresholds.json](docs/evaluation/match_thresholds.json).

Source revisions:

| Source | Revision |
| --- | --- |
| Britannica dataset | `NationalLibraryOfScotland/encyclopaedia_britannica_illustrated` at `309f765b1ecc83e0a7f7762e44b4a927a7555443` |
| Britannica manifest sha256 | `779542e078756874f23fa6971d7d8a2d8635ad6d9d9484e1deb607d94a28e396` |
| Britannica Parquet sha256 | `08f167015db23cb027995b2b6a6bc953b01d7c1ddf667de950465cc2b601af5c` |
| Sample | 100 scans, seed 20261016 |
| Wikipedia snapshot | `wikimedia/structured-wikipedia` at `417c267bb457fa645c22eb3b5c77764963194c70` |

## Results

All numbers come from the full run of 2026-10-18, 13:13 to 13:26 UTC.
Each number links to the stage summary that records it.

Extraction ([artifacts/extract/summary.json](artifacts/extract/summary.json)):

- Parse read 98 of 100 scans.
- 2 scans failed: `train:452` and `train:2243`. Parse returned an incomplete reply at temperature 0. The error details are in [artifacts/runs/failures.jsonl](artifacts/runs/failures.jsonl).
- Page status: 89 text pages, 5 plates, 4 blank or sparse pages.
- 241 entries from Parse text: 159 with a headword, 82 continuations, 2 joined across pages.

Correction ([artifacts/correct/summary.json](artifacts/correct/summary.json), [docs/evaluation/ocr-correction.md](docs/evaluation/ocr-correction.md)):

- Super VL corrected 1147 of 1148 requested text blocks. 1 block failed and kept the Parse text.
- The corrected text gives 249 entries.
- On 29 hand-transcribed blocks from 15 scans, the character error rate fell from 12.2% to 1.8%. The word error rate fell from 25.1% to 2.9%.

Article associations ([artifacts/match/summary.json](artifacts/match/summary.json), [docs/evaluation/match-calibration.md](docs/evaluation/match-calibration.md)):

- 201 entries were searched. 48 were skipped: 44 have fewer than 150 characters, 4 have no headword and short text.
- 86 entries have an accepted article. 115 were rejected.
- 2 articles are selected twice (page IDs 603624 and 82889).
- On 60 hand-labelled entries, the cross-validated accept rule has precision 0.62, recall 0.56, F1 0.59.
- An extra experiment adds Super VL title searches to the match stage. On the same 60 labels, F1 rose from 0.613 to 0.667. This code is on branch `match-llm-titles` (commit `fb93610`) and is not in the full run. See [docs/evaluation/match-llm-titles.md](docs/evaluation/match-llm-titles.md) on that branch.

Comparison method ([artifacts/compare/summary.json](artifacts/compare/summary.json), `src/nemotron_challenge/compare.py`):

- Text units: words in lower case, letters only, at least 3 letters.
- Method: word frequencies per pair, Jaccard overlap of the 100 most frequent terms, cosine of relative frequencies, and distinctive terms by log-odds with an informative Dirichlet prior (Monroe, Colaresi and Quinn 2008).
- Each distinctive term carries one source snippet from each side.
- Exclusions: stop words. Britannica tokens outside the reference vocabulary count as "unverified" and stay out of the term lists. The unverified rate is 7.5%.
- Text changes: long s to s (18 changes) and historical spelling (1 change). The log is in [artifacts/compare/normalisation_log.jsonl](artifacts/compare/normalisation_log.jsonl).
- 86 pairs, 86 Britannica entries, 84 distinct Wikipedia articles.
- Mean frequency cosine 0.24. Mean top-term Jaccard 0.06.

Index and agent ([artifacts/index/summary.json](artifacts/index/summary.json), [artifacts/agent/runs.jsonl](artifacts/agent/runs.jsonl)):

- LanceDB holds 692 Britannica passages and 856 Wikipedia passages from 84 articles.
- 45 Hermes question runs are saved. The last full 8-question run (`2026-10-18T124947Z`) completed all 8 questions. 6 passed the automatic checks.

Analysis, plots, and source records:

- Plots: [artifacts/compare/plots/distinctive-britannica.svg](artifacts/compare/plots/distinctive-britannica.svg), [artifacts/compare/plots/distinctive-wikipedia.svg](artifacts/compare/plots/distinctive-wikipedia.svg).
- Pair records with article page IDs, revision IDs, and checksums: [artifacts/compare/pairs.jsonl](artifacts/compare/pairs.jsonl).
- Matches and candidates: [artifacts/match/matches.jsonl](artifacts/match/matches.jsonl), [artifacts/match/candidates/](artifacts/match/candidates/).
- Raw Parse and Super VL replies: [artifacts/extract/raw/](artifacts/extract/raw/), [artifacts/correct/raw/](artifacts/correct/raw/).
- Quote checks: [artifacts/evaluate/quote_checks.json](artifacts/evaluate/quote_checks.json).

## Case studies

The cases are listed in [docs/evaluation/cases.json](docs/evaluation/cases.json) and [artifacts/evaluate/summary.json](artifacts/evaluate/summary.json).

| Case | Classification | Run record | Repair run |
| --- | --- | --- | --- |
| [S1-heat](artifacts/evaluate/cases/S1-heat.md) | success | `2026-10-18T114003Z/q01-heat` | none |
| [S2-willin-wrong-match](artifacts/evaluate/cases/S2-willin-wrong-match.md) | success | `2026-10-18T114003Z/q07-willin` | `2026-10-18T115609Z/q07-willin`, match repaired |
| [S3-locomotive-missing](artifacts/evaluate/cases/S3-locomotive-missing.md) | success | `2026-10-18T114003Z/q06-locomotive` | none |
| [F1-philology-false-absence](artifacts/evaluate/cases/F1-philology-false-absence.md) | failure | `2026-10-18T114003Z/q05-philology` | `2026-10-18T115609Z/q05-philology`, partly fixed |
| [F2-corpus-brit-inference](artifacts/evaluate/cases/F2-corpus-brit-inference.md) | failure | `2026-10-18T114003Z/q04-corpus` | `2026-10-18T115609Z/q04-corpus`, fixed |
| [F3-heat-no-rules-edition](artifacts/evaluate/cases/F3-heat-no-rules-edition.md) | failure | `2026-10-18T113829Z-trial/q01-heat-nopolicy` | `2026-10-18T115609Z/q01-heat`, fixed |

The raw Hermes events of each run are in `artifacts/agent/runs/<run_id>/`.
The failed first attempts stay in their own run folders. The repair runs have separate run IDs.
The case runs use the first pipeline (Parse text, title-rule match). The later runs use the corrected text and the model match.

## Limits

What we tested:

- 140 unit and fixture tests pass. They test contracts and setup behavior. They do not prove OCR accuracy or retrieval quality.
- OCR quality: 29 hand-transcribed blocks from 15 scans.
- Match quality: 60 hand-labelled entries, with the model scores hidden during labelling.
- Agent quotes: an automatic check compares each quote with the tool results. 3 flagged quotes are checker false alarms (odd quote marks, OCR line-break hyphens).

What remains uncertain:

- One labeller (the coding agent) made the gold transcriptions and the match labels. Nobody did a second review.
- The test half of the match labels has 30 entries. One entry changes F1 by about 0.03.
- The vocabulary rate and the frequency cosine are proxies, not accuracy measurements.
- The case runs record code revision `6a8987c` with uncommitted changes, so the exact code of those runs is not in Git.
- The agent answer varies between runs. For NAXOS, one run rejected "Naxos (Crete)" and a later run accepted it (inference: the Britannica coordinates point to the Aegean island).

Known failure modes:

- Parse returns incomplete replies on 2 dense scans.
- Super VL can stop at the token limit (`finish_reason=length`) on long blocks. The stage then keeps the Parse text.
- The reranker margin rule rejects some correct matches when two candidates are close (HEAT, margin 0.15).
- BM25 does not always return the main article (COINAGE, ERFURT).
- Hermes can stop at the turn limit (`2026-10-18T115609Z/q06-locomotive`, exit code 1 after 20 tool calls).
- The automatic agent checks are text rules. They do not test unsupported metadata, such as an invented edition year (F3).

Possible next steps:

- Merge the LLM title searches and calibrate the thresholds again on the new candidates.
- Add a second labeller for the OCR and match labels.
- Repeat the agent questions several times and report the spread.
- Split Parse requests for dense scans and retry the 2 failed scans.
