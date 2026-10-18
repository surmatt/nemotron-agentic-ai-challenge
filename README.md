# Surmatotron: Nemotron Agentic AI Challenge

We compare historical Britannica scans with Wikipedia and use a Hermes agent to answer comparison questions with source evidence.

Our solution adds OCR correction, article matching, vocabulary analysis, difference summaries, semantic search, and a visual workbench to the challenge starter.
The outputs include a static website, compiled LaTeX documents, saved model replies, and three success and three failure case studies.

- Team: Surmatotron
- Repository: <https://github.com/surmatt/nemotron-agentic-ai-challenge>. Final commit: pending.
- Video (3 to 5 minutes): pending.
- Static website: [artifacts/site/index.html](artifacts/site/index.html), from the Saved run.
- Compiled LaTeX documents: [artifacts/site/latex/](artifacts/site/latex/), 98 PDFs with their `.tex` sources.
- Case studies: [three successes and three failures](#case-studies).
- Models: Parse 3.5, Super 3.5 VL (Super VL below), Embed VL, and Rerank VL. See [Models and serving settings](#models-and-serving-settings) for the model IDs.

## First and latest results

The table compares our First run, before OCR correction and model matching, with e2e4, our latest end-to-end run.

- First run: 11:36 UTC on 2026-10-18, Parse text, lexical title rule, [`artifacts/archive/2026-10-18-initial/`](artifacts/archive/2026-10-18-initial/).
- e2e4: 15:46 UTC on 2026-10-18, commit `61e8d29` with uncommitted changes, [stage summaries](docs/evaluation/e2e4/).

The [run index](#run-index) lists all runs in this README and defines the terms.

| Result | First run | e2e4 |
| --- | --- | --- |
| Scans parsed | 98 of 100 | 98 of 100 |
| Text blocks corrected by Super VL | Not run | 1,147 of 1,148 |
| Entries | 241 from Parse | 241 from Parse, 250 after correction |
| Wikipedia matches | 57 accepted, 131 rejected, 188 searched | 176 accepted, 25 rejected, 201 searched |
| Compared pairs / distinct Wikipedia articles | 57 / 55 | 176 / 171 |
| Britannica tokens outside the vocabulary | 19.3% | 6.9% |
| Mean word-frequency cosine of the pairs | 0.17 | 0.22 |
| Indexed Britannica / Wikipedia passages | Not run | 687 / 1,948 |
| Difference summaries | Not run | 174 of 176 pairs. Both quotes found for 612 of 658 differences |
| Hermes questions completed / automatic passes | 8 of 8 / 8 in run `114003Z` (see the inference note), older question set | 8 of 8 / 5 |
| Scan pages / compiled PDFs | No record | 98 / 98, no LaTeX failures |

e2e4 adds Super VL OCR correction, Embed VL and Rerank VL matching with Super VL search terms, and no margin gate.
Accepted matches rose from 57 to 176. Nobody has measured the precision of e2e4, so more accepted matches do not prove better matching.

The website, pair records, and difference summaries in `artifacts/` come from the Saved run (86 accepted matches), not from e2e4.
Git keeps only the e2e4 stage summaries, in [`docs/evaluation/e2e4/`](docs/evaluation/e2e4/).

Notes:
- Sources for the First run: the [match summary](artifacts/archive/2026-10-18-initial/match/summary.json), the [compare summary](artifacts/archive/2026-10-18-initial/compare/summary.json), and the extract failures for scans 452 and 2243 in [`artifacts/runs/failures.jsonl`](artifacts/runs/failures.jsonl).
  The archive keeps only the match and compare outputs. The First run had no correction or index stage.
- Inference: agent run `2026-10-18T114003Z` started about 3 minutes after the First run, so it used the First run outputs. Its record does not say which match and compare outputs it read.
  The question set changed before e2e4.
- The correct stage splits the corrected text into entries again, and e2e4 has 250 entries after that step. The run record does not give the cause of each of the 9 added entries.
- e2e4 ran the eight stages of revision `61e8d29` in about 12 minutes. The `summarize` stage did not exist in that revision. Each stage exited with code 0.
  Before the run, 169 tests passed. The live check passed for Wikipedia, Parse, the retrieval service, and Super VL.
  The `summarize` stage ran on the e2e4 work directory after the eight-stage run. Inference: it used commit `6944d4d`.
- See [the run report](docs/evaluation/e2e-runs.md) for thresholds, the match-output checksum, and the ten failure records.
  The pipeline continued without those results.

Coverage in e2e4:
- 89 pages are text pages, 5 are plates, and 4 are blank or sparse. 2 scans failed in Parse.
- The 241 Parse entries are 159 headword entries and 82 continuations. The extract stage joined 2 continuations across pages.
- The match stage skipped 49 of the 250 entries and searched 201.
- The 176 pairs use 171 distinct Wikipedia articles. 5 articles occur in two pairs.

## How we checked

- Match: the coding agent labeled 60 entries with the model scores hidden. We measured each accept rule against these labels ([match-calibration.md](docs/evaluation/match-calibration.md)). The best rule had precision 0.82 and recall 0.53 (fitted on all 60, optimistic). No labels measure the e2e4 rule.
- OCR: we scored the Parse text and the Super VL text against the OCR gold set of 30 blocks from 15 scans ([ocr-correction.md](docs/evaluation/ocr-correction.md)). The character error rate fell from 12.2% (Parse) to 1.8% (Super VL) on the 29 blocks with text.
- Comparison: each pair record cites a snippet from both sources, and the corpus counts use only accepted matches ([pairs.jsonl](artifacts/compare/pairs.jsonl)).
- Citation: the `evaluate` stage checks agent quotes against tool results, and the `summarize` stage checks each quote against its source. The team read the sources for the six case studies ([cases.json](docs/evaluation/cases.json)).

## Case studies

All six case studies come from agent runs that started at 11:38 and 11:40 UTC, after the First run.
These runs came before OCR correction and model matching. They do not test the e2e4 pipeline.
An automatic pass checks text rules only. All three failure case studies passed their automatic checks: F1 and F2 in run `114003Z`, F3 in run `113829Z-trial`. The team classified them as failures after source review.
[docs/evaluation/cases.json](docs/evaluation/cases.json) records each case, its run, its reason, and its repair.

| Classification | Case | Agent run | What it shows |
| --- | --- | --- | --- |
| Success | [HEAT comparison](artifacts/evaluate/cases/S1-heat.md) | `2026-10-18T114003Z` | Reads both sources and cites evidence for different accounts of heat |
| Success | [WILLIN wrong match](artifacts/evaluate/cases/S2-willin-wrong-match.md) | `2026-10-18T114003Z` | Rejects a wrong Wikipedia match instead of trusting the match stage |
| Success | [Missing locomotive entry](artifacts/evaluate/cases/S3-locomotive-missing.md) | `2026-10-18T114003Z` | Reports missing evidence without filling the gap from memory |
| Failure | [PHILOLOGY false absence](artifacts/evaluate/cases/F1-philology-false-absence.md) | `2026-10-18T114003Z` | OCR prevents discovery, and the agent claims the entry is absent. Repair: fuzzy headword search and an OCR headword variant in matching (partly fixed) |
| Failure | ["Brit." interpretation](artifacts/evaluate/cases/F2-corpus-brit-inference.md) | `2026-10-18T114003Z` | Explains a printed abbreviation as an OCR fragment without reading the source |
| Failure | [Unsupported edition](artifacts/evaluate/cases/F3-heat-no-rules-edition.md) | `2026-10-18T113829Z-trial` | States an edition that no tool result supports. Repair: the evidence rule, see S1 |

## Known limits

- Two of the 100 scans did not yield complete Parse replies. The website and PDFs cover 98 scans.
- One labeler, the coding agent, made the OCR gold set and the match labels. Nobody did a second review.
- The OCR gold set excludes tables, formulas, pictures, and headers.
- The fitted calibration scores come from the margin-gate rule on the previous candidate set. They do not measure the e2e4 candidate set or the no-margin rule. The precision of e2e4 matching is unknown.
- Inference: the e2e4 thresholds (title similarity 0.0, no margin gate) accept more wrong pages than the margin-gate rule ([e2e-runs.md](docs/evaluation/e2e-runs.md)).
- Automatic agent checks and quote checks need human review. The e2e4 HEAT and PHILOLOGY answers remain open review items.
- The case studies come from runs before OCR correction and model matching. e2e4 generated no case studies.
- Summary quote checks show that the text occurs, not that it supports the claim. Selected passages cannot prove that a whole source omits a topic.
- Nobody has reviewed the subject judgments of the difference summaries.
- The vocabulary and cosine numbers are proxies, not accuracy measurements.
- A zero exit code does not mean complete coverage, correct matches, or six reproduced case studies. Check the stage summaries and failure records.
- The e2e4 evaluate record gives Python 3.12.0 and macOS 14.3 arm64. No record lists the installed packages.

## Submission evidence

This README follows the [submission template](templates/submission.md). Each case study follows the [case-study template](templates/case-study.md).
The [LaTeX template](templates/page.tex) separates historical text from its source record.

The repository includes these deliverables. All except the e2e4 copies come from the Saved run.

| Deliverable | Evidence |
| --- | --- |
| Static website and compiled documents | [Site](artifacts/site/index.html), [LaTeX sources and PDFs](artifacts/site/latex/), [build summary](artifacts/site/summary.json) |
| Comparison analysis | [Pair records](artifacts/compare/pairs.jsonl), [corpus counts](artifacts/compare/corpus.json), [plots](artifacts/compare/plots/), [normalization log](artifacts/compare/normalisation_log.jsonl) |
| Difference summaries | [Summaries](artifacts/summarize/summaries.jsonl), [summary](artifacts/summarize/summary.json), [raw replies](artifacts/summarize/raw/): 86 of 86 Saved-run pairs, both quotes found for 320 of 339 differences |
| Source and model records | [Raw Parse replies](artifacts/extract/raw/), [OCR corrections](artifacts/correct/), [Wikipedia candidates and articles](artifacts/match/), [Hermes runs](artifacts/agent/runs/) |
| Evaluation | [Case studies and repairs](docs/evaluation/cases.json), [evaluation summary](artifacts/evaluate/summary.json), [end-to-end report](docs/evaluation/e2e-runs.md), [e2e4 stage summaries](docs/evaluation/e2e4/) |

Git ignores the `artifacts-e2e*/` work directories. They exist only on the machine that ran them.
[`docs/evaluation/e2e4/`](docs/evaluation/e2e4/) keeps a copy of each e2e4 stage summary and the e2e4 failure log.

## Run index

Most pipeline-run numbers in this README belong to one of these runs. All runs took place on 2026-10-18.
The exceptions are the corrected-text run in section 1, which has no run record, and the `summarize` run on `artifacts/` at 15:44 UTC.
Evaluations and agent runs name their own records.

| Label | Finished (UTC) | Code | Folder | Entry text and match rule |
| --- | --- | --- | --- | --- |
| First run | 11:36 | First team stage code. The record has no commit. | [`artifacts/archive/2026-10-18-initial/`](artifacts/archive/2026-10-18-initial/) | Parse text, lexical title rule |
| Parse-text baseline | 11:55 | Inference: `e93e9d3` with uncommitted changes. Its summary has OCR headword variants, which `2c65ef1` first committed. | [`artifacts/match-parse-text-2026-10-18/`](artifacts/match-parse-text-2026-10-18/), [`artifacts/compare-parse-text-2026-10-18/`](artifacts/compare-parse-text-2026-10-18/) | Parse text, lexical title rule |
| Saved run | 13:17 (match) | `6a8987c` with uncommitted changes | `artifacts/` | Super VL text, margin-gate rule |
| e2e3 | 13:52 | `c60de4b` with uncommitted changes, before PR #8 | `artifacts-e2e3/` (not in Git) | Super VL text, margin-gate rule |
| e2e4 | 15:46 | `61e8d29` with uncommitted changes | `artifacts-e2e4/` (not in Git), copies in [`docs/evaluation/e2e4/`](docs/evaluation/e2e4/) | Super VL text, Super VL search terms, no margin gate |

The First run accepted 57 matches and the Parse-text baseline accepted 53 with the same rule.
Inference: the match code changed between the two runs. The baseline adds OCR headword variants (PHILLOOGY → Philology) and removes list pages (Coinage, Willin').
The code revisions come from the evaluate records. The First run and the Parse-text baseline have no evaluate record.

Terms:
- e2e: end-to-end. e2e3 and e2e4 are isolated runs of all stages in new work directories.
- Entry: a Britannica text unit. A headword starts it, or it continues text from the page before.
- Lexical title rule: accept a Wikipedia page when its title similarity to the headword is at least 0.85. This rule uses no retrieval models.
- Margin gate: the top reranked candidate must beat the second candidate by a set logit margin. The margin-gate rule used a margin of 0.5.
- Super VL search terms: a title guess and extra search terms that Super VL writes for each entry. The match stage sends them as one more BM25 query. PR #8 (`match-llm-terms`) added these terms and removed the margin gate.
- Logit: the raw relevance score of Rerank VL. A higher logit means a more relevant page.
- Tokens outside the vocabulary: tokens that are not in the cached Wikipedia text or in the system word list.
- Word-frequency cosine: the cosine of the word-count vectors of the two texts in a pair.
- Automatic pass: a text-rule check on the model ID, completion, tool use, cited entry and revision IDs, and the expected behavior. It does not check quotes or facts. The `evaluate` stage checks quotes separately.

## Team solution

Our pipeline has nine stages. Run each one with `uv run nemotron-challenge run <stage>`.
[docs/team-pipeline.md](docs/team-pipeline.md) describes the method of each stage.

| Stage | What it does | Models |
| --- | --- | --- |
| `extract` | Parses each scan, keeps the raw reply, removes page headers, footers, and page numbers, and splits entries at headwords | Parse 3.5 |
| `correct` | Corrects the Parse text of each block from an enlarged crop of the scan | Super VL |
| `match` | Gets BM25 candidates (headword, cleaned frequency keywords, Super VL search terms), ranks them with Rerank VL, and accepts the top page when logit, cosine, and title similarity pass the thresholds in [section 2](#2-matching-with-embed-vl-and-rerank-vl) | Super VL, Embed VL, Rerank VL |
| `compare` | Compares word frequencies with log-odds and cites a snippet from both sources | – |
| `index` | Embeds Britannica and Wikipedia passages and stores them with citations in LanceDB | Embed VL |
| `summarize` | Lists the key differences of each pair with one quote per side, and checks each quote against the source | Super VL, Embed VL |
| `agent` | Runs Hermes with five team tools (search, semantic search, compare, read, corpus) and evidence rules | Super VL |
| `site` | Builds a static website and one compiled LaTeX document per scan | – |
| `evaluate` | Checks quotes against tool results and writes the case studies when their agent runs are present | – |

The vocabulary comparison uses the accepted matches, not all extracted entries.
It compares word frequencies with log-odds z-scores and an informative Dirichlet prior.
Corpus counts include each matched Wikipedia article once.
Tokenization keeps lowercase letter sequences of at least three letters and removes stop words.
The stage logs each abbreviation, long-s, and historical-spelling change in the Britannica text.
The stage counts words outside the reference vocabulary as unverified. It removes them from the comparison term lists.
The reference vocabulary combines cached Wikipedia text with the system word list, if the system has one.
Source snippets keep the source wording. The generated difference summaries have a separate label.

### 1. Super VL correction of the Parse text

We tried to change the Parse input first.
Splitting each scan into columns made Parse worse. With overlap-window scoring, the character error rate was 20.2% for the split pages and 12.8% for the whole pages. The split was worse on 22 of 29 blocks ([`artifacts/split_eval-2026-10-18/eval.json`](artifacts/split_eval-2026-10-18/eval.json)).
We also tried upscaling the scans. No run record keeps that test.

After Parse 3.5, Super VL reads each text block again. Its input is an enlarged crop of the block and the Parse text.
We measured the result against the OCR gold set: reference transcriptions of 30 blocks from 15 scans, made by the coding agent.
29 of the 30 blocks contain text, so the scores use 29 blocks ([ocr-correction.md](docs/evaluation/ocr-correction.md)).

| Text | Character error rate | Word error rate | Blocks better than Parse |
| --- | --- | --- | --- |
| Parse 3.5 | 12.2% | 25.1% | – |
| Parse 3.5 + Super VL (block crop) | 1.8% | 3.0% | 28 of 29 |
| ... + dictionary long-s rule (used) | 1.8% | 2.9% | 28 of 29 |

- Super VL lowers the character error rate from 12.2% to 1.8%, a factor of 6.8.
- With reasoning on, the character error rate was 2.9% instead of 1.8% (28 blocks, because one reasoning call hit the token limit), and each block took 13.9 s instead of 1.1 s.
- A whole-page input gave a character error rate of 24.9%. The model often transcribed the wrong region.
- A corrected-text run with the lexical title rule accepted 80 matches, against 53 in the Parse-text baseline. Inference: the correction helps matching. No labels measure the precision of the 80 matches.
  Britannica tokens outside the vocabulary fell from 18.8% to 10.6%. Only the [ocr-correction.md](docs/evaluation/ocr-correction.md) table keeps the 80 and 10.6% values. No run summary keeps that corrected-text run.
- Example: the headword "WILLIN" became "WILLIAM", and NAXOS now reads "capital of the Isle of Naxos" instead of "capital of the lake of Naoxe".

### 2. Matching with Embed VL and Rerank VL

e2e4 used these thresholds from `docs/evaluation/match_thresholds.json`: logit ≥ -10.0, cosine ≥ 0.15, and title similarity ≥ 0.0, with no margin gate.
The rule takes the top reranked page when its logit, cosine, and title similarity pass the thresholds.
The calibration code now fits the thresholds for the best F2 score, which weighs recall twice as much as precision. No calibration has run with F2 yet.

The results below come from the 60 labeled entries on the previous candidate set
([docs/evaluation/match-calibration.md](docs/evaluation/match-calibration.md)).
43 of the 60 entries have at least one correct candidate.
Only the last two rows of the second table use the margin-gate rule.

| Ranker | First candidate correct (43 labeled entries) |
| --- | --- |
| BM25 | 28% |
| Embed VL cosine | 49% |
| Rerank VL logit | 65% |

| Accept rule | Precision | Recall | F1 |
| --- | --- | --- | --- |
| Lexical title rule | 0.71 | 0.47 | 0.56 |
| Rerank VL first candidate, logit ≥ -6, title ≥ 0.75 (first reranker run) | 0.79 | 0.44 | 0.57 |
| Margin-gate rule, thresholds fitted per fold (two-fold cross-validation) | 0.62 | 0.56 | 0.59 |
| Margin-gate rule, margin ≥ 0.5, cosine ≥ 0.15, fitted on all 60 (optimistic) | 0.82 | 0.53 | 0.65 |

- The Saved run accepted 86 of 201 searched entries with the margin-gate rule.
- Rerank VL found articles that the lexical title rule missed. For example, COINAGE matches "Coining (mint)".
- It also rejected wrong title matches, such as NAXOS → "Naxos (Crete)".
- The margin-gate rule rejected HEAT → "Heat" because the margin to the second candidate was 0.15.
  The e2e4 rule removes that condition.

### 3. LanceDB passage index and semantic search

The `index` stage stores Embed VL passage vectors with their citations in LanceDB.
The Saved run embedded 692 Britannica passages and 856 Wikipedia passages from 84 accepted Wikipedia articles in about 40 seconds.
The Hermes tool `challenge_semantic_search` searches this index by meaning.

- Before we added fuzzy headword search, word search could not find the entry with the OCR headword "PHILLOOGY" (E0019 in run `114003Z`, E0021 in the Saved run).
  Commit `f9acf78` records that semantic search for "philology" finds this entry.
- A manual query, "how coins were struck with dies and a hammer", returned the Wikipedia article "Coining (mint)" and the Britannica entry COINAGE. No saved output records this query.
- In agent run `2026-10-18T132500Z` (q06), Hermes called `challenge_semantic_search` after word search found no "locomotive" entry.
  It got Wikipedia passages on early steam locomotives and the Britannica STEAM-ENGINE entry. It reported that Britannica has no locomotive entry.
- In the first full agent run with the tool (`2026-10-18T131943Z`), the tool call in q06 failed with `semantic search failed: IndexError`.
  We traced the error to the Hermes environment variables (`PYTHON*`, `VIRTUAL_ENV`), which reached the project Python (commit `f9acf78`).
  The plugin removes these variables. It reports the exit code and the last error line.

### 4. Hermes agent on the improved evidence

Hermes runs `nvidia/Nemotron-3.5-Super-VL` through Nebius Token Factory with five team tools.
In e2e4, all 8 questions completed and 5 passed the automatic checks.
The HEAT question passed in e2e3 but failed the e2e4 automatic check.
The quote checker also flagged the e2e4 PHILOLOGY answer.

Agent run `2026-10-18T124947Z` ran at 12:49 UTC on corrected text and model matching.
The Saved run outputs in `artifacts/` finished later, at 13:13 to 13:18. Inference: run `124947Z` used the same entries and match scores, because its entry IDs and NAXOS scores equal the Saved run values.
The run completed all 8 questions and passed 6 automatic checks.
The examples below describe that run, not e2e4:

- With the corrected text, the agent quotes readable sources. For NAXOS it quotes "capital of the Isle of Naxos, opposite the Isle of Paros" and places the town in the Cyclades, not in Crete.
- It questions weak matches: it reports that the PHILOLOGY pair and the WILLIAM pair do not describe the same subject.
- When an entry has no accepted match (HEAT), it says that the comparison evidence is missing.

### 5. Difference summaries

We added the `summarize` stage after word-frequency comparison.
Super VL reads each pair and returns a subject judgment (do both texts describe the same subject), a short overview, and up to five differences in facts, explanations, scope, or emphasis.
For each difference, the prompt asks for one exact quote from each source.

- The model reads the corrected Britannica entry and the Wikipedia article.
- For articles longer than 12,000 characters, Embed VL selects relevant passages. The stage reuses stored LanceDB vectors. Without retrieval, the stage uses the first passages and labels that fallback.
- The code checks each quote against its source text and records offsets and Wikipedia passage IDs.
- `quotes_found` means that both quotes occur in the sources. It does not prove that the quotes support the claims. Claims, the overview, and the subject judgment remain model inference.
- Raw replies, prompts, and passage selections stay separate from derived summaries. The stage keeps failed replies and writes no summary for them.

On the e2e4 work directory, the subject judgments were 75 yes, 78 partly, and 21 no.
The summaries in `artifacts/summarize/` ran without stored index vectors. Embed VL selected the passages for 29 of the 86 pairs.

Run `uv run nemotron-challenge run summarize` after `compare` and `index`.
Corpus outputs go to `artifacts/summarize/summaries.jsonl`, `summary.json`, and `raw/`.
The workbench shows the difference summary and both quote checks in the Comparison tab.
See [the stage method and limits](docs/team-pipeline.md) for details.

## Infrastructure

The Britannica scans enter our CPU workspace for ingestion and caching.
Our tools call the shared Parse and Wikipedia APIs and our GPU service for Embed VL and Rerank VL.
Hermes runs in the CPU workspace and calls Super VL through Token Factory.

![Participant infrastructure and Britannica ingestion](docs/assets/nebius-participant-infrastructure.png)

[Full-size PNG](docs/assets/nebius-participant-infrastructure.png) · [Editable SVG](docs/assets/nebius-participant-infrastructure.svg)

## Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
Use Python 3.12.
Clone the repository and open a terminal in its root directory.

```sh
uv sync --locked
cp .env.example .env
uv run nemotron-challenge doctor --offline
uv run nemotron-challenge stages
```

The offline check tests the local setup. It does not call the services.
Coding agents read [AGENTS.md](AGENTS.md) for the project rules.

### Get the source scans

```sh
uv run nemotron-challenge data show
uv run nemotron-challenge data fetch
```

All teams use the same 100 scans and source checksums.
The first fetch downloads a pinned Parquet file of about 357 MiB.
The loader writes the selected scans to `data/raw/britannica`.
It leaves the source cache unchanged.

The organizer built a shared BM25 keyword index over 7,182,883 canonical English Wikipedia articles from a fixed snapshot.
We search it through the [Wikipedia API](docs/wikipedia-api.md) and fetch article text with the paginated article API.
The shared index supplies candidates, not verified Britannica matches.
Our LanceDB index holds our chosen evidence and vectors, separate from the shared keyword index.
Read the [API guide](docs/wikipedia-api.md) for client calls, pagination, and citation metadata.

### Set up the models

The organizer supplies Parse 3.5 and the Wikipedia API.
We deploy Embed VL and Rerank VL on Nebius AI Cloud with the [Docker recipe](docs/model-service.md).
Super VL runs through a separate Nebius Token Factory account.
Set the URLs and keys in `.env`.
Keep that file out of Git.
Use the [Hermes guide](docs/hermes.md) to install the team plugin and model settings.

```sh
uv run nemotron-challenge doctor --live
```

The live check tests service access and model catalogs.
Read its output for missing settings and test limits.

## Reproduce the pipeline

Complete the source, model, and Hermes setup above.
Install `tectonic` to compile the documents.
Use the locked Python packages in [uv.lock](uv.lock).

```sh
uv sync --locked
uv run --locked pytest
uv run --locked nemotron-challenge doctor --live
uv run --locked nemotron-challenge data show
uv run --locked nemotron-challenge data fetch

for stage in extract correct match compare index summarize agent site evaluate; do
  uv run --locked nemotron-challenge run "$stage" --work-dir artifacts-reproduce || break
done
uv run --locked nemotron-challenge stages --work-dir artifacts-reproduce
```

These commands run the current nine-stage pipeline in a separate work directory.
They call live services and can incur charges.
They are reproduction instructions, not a claim that a new run has passed.
To repeat the stage sequence recorded for e2e4, use revision `61e8d29` and omit `summarize`. The e2e4 run also had uncommitted changes.
Model output and entry counts can vary between runs.

Inspect each stage's `summary.json` and `runs/failures.jsonl`.
In a new work directory, `evaluate` checks the new agent runs. It does not reproduce the six selected cases without their original run records.
Keep the submitted cases linked to their saved runs in `artifacts/`.

Serve the new static site:

```sh
uv run python -m http.server 8791 --bind 127.0.0.1 --directory artifacts-reproduce/site
```

Open <http://127.0.0.1:8791/>.
See [the pipeline guide](docs/team-pipeline.md) for stage methods and [the challenge brief](docs/challenge.md) for deliverables.
The submission requires the repository and a video of 3 to 5 minutes.

### Models and serving settings

| Role | Model ID | Revision / service |
| --- | --- | --- |
| Extraction | `nvidia/nemotron-3.5-parse` | Organizer endpoint |
| Embedding | `nvidia/llama-nemotron-embed-vl-1b-v2` | `582e3bf72aee355e3c59ed89de53543c5b0657ee`, team Nebius deployment |
| Reranking | `nvidia/llama-nemotron-rerank-vl-1b-v2` | `b8a9987b05b75db5ad949c825cbcbf6eb7c48b5a`, team Nebius deployment |
| OCR correction, search terms, summaries, Hermes | `nvidia/Nemotron-3.5-Super-VL` | Nebius Token Factory |

| Tool | Version in e2e4 |
| --- | --- |
| Hermes Agent | v0.22.2 (2026.9.24) |
| Tectonic | 0.17.0 |

The retrieval recipe pins Python 3.11, PyTorch 2.8.0, CUDA 12.8, and Transformers 4.56.2.
Its Nebius Serverless command uses one RTX PRO 6000 GPU.
See [the service recipe](docs/model-service.md) for the image digest, package hashes, and runtime checks.
Correction and summarization use temperature 0 with reasoning off.

The workspace uses Python 3.12. `uv.lock` pins the application versions.
Keep keys and private service settings in `.env`, outside Git.

### Source revisions

| Source | Pinned identifier |
| --- | --- |
| Britannica dataset | `309f765b1ecc83e0a7f7762e44b4a927a7555443` |
| Britannica manifest hash (`manifest_sha256`) | `779542e078756874f23fa6971d7d8a2d8635ad6d9d9484e1deb607d94a28e396` |
| Wikipedia snapshot | `417c267bb457fa645c22eb3b5c77764963194c70` |

The [manifest](src/nemotron_challenge/resources/britannica-manifest.json) fixes all 100 scans and their image checksums.
Wikipedia records retain page IDs, article revision IDs, and text checksums.
Raw replies, derived source text, and generated comparisons remain separate.

## Visual workbench

The workbench shows the pipeline on one scan at a time.
Upload a scan and run the six steps: extract, correct, match, compare, summarize, and document.
The views show the scan with block boxes, the Super VL corrections, the Wikipedia candidates and scores, the term comparison, the difference summary with quote checks, the LaTeX document, and the raw model replies.

You need Node.js 20.19 or later.
For PDFs, install `tectonic` (`brew install tectonic` on macOS). Without it, the document step writes `.tex` files only.
Start the backend and the frontend with one command.

```sh
make run
```

Open <http://127.0.0.1:5173>.
The command installs missing Python and npm packages.
It starts the backend on port 8790 and the Vite dev server on port 5173.
Press Ctrl-C to stop both.
If one process stops, the command stops the other.

To run only the backend, install the extra packages and build the frontend one time.

```sh
uv sync --locked --extra ui
npm --prefix ui ci
npm --prefix ui run build
```

Start the server.

```sh
uv run nemotron-challenge ui
```

Open <http://127.0.0.1:8790>.
Use `--port` to change the port.
Use `--work-dir` to change the work directory. The default is `artifacts`.

- **Workbench tab:** drop a JPEG or PNG scan, then click **Run all steps** or run one step at a time. The server keeps each upload in `artifacts/ui/uploads/<id>/`.
- **Corpus tab:** browse the 100 pinned scans with the saved stage outputs from `artifacts/`. Click **Run live in workbench** to copy a scan into the workbench and run the steps on it.
- **Re-run a stage:** click **Re-run** on a stage card. The stage runs again, then each later stage that ran before. The `+N` badge shows the number of other stages that run with it. Hold the pointer on the button to see their names. Earlier outputs move to `history/<time>/` in the upload folder.
- **Apply a new match rule:** in an upload's Matching tab, click **Apply current rule (reuse scores)**. This updates the saved decisions from the existing candidate scores without search or model calls. It fetches full text for the Wikipedia articles that the new rule accepts and rebuilds later outputs that ran. Changed entry text requires a full `match` re-run.
- **Re-run on a corpus scan:** the workbench copies the scan and reuses the saved Parse and Super VL replies of the corpus run. Then it runs the chosen stage and the later stages. Match has no per-scan saved output, so a compare re-run also runs match. The corpus artifacts stay unchanged.
- **Check services:** runs the live check on Parse, Super VL, the retrieval service, and the Wikipedia API.
- **Difference summary:** the summarize step calls Super VL and shows the generated overview, subject judgment, differences, and source quotes in the Comparison tab. Each quote has a found/not-found check. Claims keep the inference label.
- **LaTeX document tab:** the document step writes one LaTeX document for the scan with the code in `site.py`, and `tectonic` compiles it. The tab shows the PDF next to the `.tex` source. On a corpus scan, the tab shows the document from the last site build.
- **Static site:** on the overview, click **Build site** to run the site stage on the saved corpus artifacts. The same command is `uv run nemotron-challenge run site`. Then click **Open static site**. The server serves it at `/site/index.html`. The first build downloads the LaTeX packages for `tectonic`, so it takes longer.

The live steps read the service URLs and keys from `.env`.
Extract calls Parse. Correct calls Super VL. Match calls Super VL, the Wikipedia API, and the retrieval service.
Summarize calls Super VL and uses the retrieval service to rank passages of long Wikipedia articles.
Compare and document run locally.
If `RETRIEVAL_BASE_URL` is not set or does not answer, match uses the lexical title rule and the step summary says so.
The Corpus tab needs `uv run nemotron-challenge data fetch` and the saved stage runs.
The Python backend loads code at startup. After changing backend code, restart `make run` before applying a new rule.

Other targets: `make install`, `make build`, and `make test`.

### Public deployment on Nebius

The team chose open access with no password.
Anyone with the URL can upload scans and run the live steps.
Each run uses the team's Parse, Super VL, and retrieval quota.
Stop the endpoint when you do not need it.

The image in `infra/workbench/` holds the built UI, the saved corpus run from `artifacts/`, and the pinned scans.
It holds no keys.
Uploads stay in the container file system. A restart of the endpoint deletes them.

Build the image from the repository root.

```sh
docker buildx build --platform linux/amd64 --load -f infra/workbench/Dockerfile -t nemotron-workbench:local .
```

Use `--build-arg ARTIFACTS_DIR=<folder>` to ship a different work directory.
Test it on your computer with the keys from `.env`.

```sh
docker run --rm -p 127.0.0.1:8790:8790 --env-file .env nemotron-workbench:local
```

Push the image to your Nebius Container Registry and create a CPU endpoint with the values from `.env`.
The script puts the API keys in a MysteryBox secret and passes the URLs as plain variables.

```sh
REGION_ID=uk-south2 REGISTRY_PATH=<registry ID without registry-> infra/workbench/deploy.sh
```

## Checks

```sh
uv run --locked pytest
```

Tests cover data contracts, clients, stage behavior, calibration, passage search, summaries, and workbench re-runs.
Fixture tests do not prove OCR accuracy, retrieval quality, or factual support.
Sections 1 and 2 link the OCR results and the match-rule results.
The 169-test count in the [end-to-end report](docs/evaluation/e2e-runs.md) comes from before the `summarize` stage. It is not a result for the current test suite.

## Background diagrams

These diagrams come from the challenge starter. They show methods that we did not implement.

The multimodal matching diagram uses Wikipedia article text as a query to find Britannica page scans.
Embed VL encodes the scans and the query, and Rerank VL ranks the candidate pages.
Our `match` stage goes the other way: it starts from Britannica entries and searches Wikipedia through the shared API.
See the [Embed VL model card](https://huggingface.co/nvidia/llama-nemotron-embed-vl-1b-v2) and [Rerank VL model card](https://huggingface.co/nvidia/llama-nemotron-rerank-vl-1b-v2) for the model contracts.

![Conceptual workflow from Wikipedia article text through Embed VL similarity search and Rerank VL to ranked Britannica pages](docs/assets/nemotron-vl-matching.png)

[Full-size PNG](docs/assets/nemotron-vl-matching.png)

The BERTopic diagram shows topic comparison with Nemotron embeddings, UMAP, HDBSCAN, term counts, c-TF-IDF, and optional Super VL topic labels.
Our comparison uses word-frequency log-odds and the difference summaries, not BERTopic.

![BERTopic with Nemotron embeddings and optional Super VL topic refinement](docs/assets/bertopic-nemotron-implementation.png)

[Full-size PNG](docs/assets/bertopic-nemotron-implementation.png) · [Editable SVG](docs/assets/bertopic-nemotron-implementation.svg)

## Licenses

The starter code uses the [MIT license](LICENSE).
Data and model weights retain their source licenses.
Read [ATTRIBUTION.md](ATTRIBUTION.md) before you share source material or model artifacts.
