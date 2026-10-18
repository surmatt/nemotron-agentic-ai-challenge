# Nemotron Agentic AI Challenge

Build an agent that compares historical Britannica pages with Wikipedia.
Work with your coding agent to complete the project stages.

This starter supplies setup code, model clients, source data contracts, and checks.
Your team builds the extraction workflow, article matching, comparisons, agent tools, and website.

## Team solution and results

Our pipeline has seven stages. Run each one with `uv run nemotron-challenge run <stage>`.
[docs/team-pipeline.md](docs/team-pipeline.md) describes the method of each stage.

| Stage | What it does | Models |
| --- | --- | --- |
| `extract` | Parses each scan, keeps the raw reply, removes page furniture, and splits entries at headwords | Parse 3.5 |
| `correct` | Corrects the Parse text of each block from an enlarged crop of the scan | Super 3.5 VL |
| `match` | Gets BM25 candidates, ranks them with the reranker, and accepts by calibrated thresholds | Embed VL, Rerank VL |
| `compare` | Compares word frequencies with log-odds and cites a snippet from both sources | – |
| `agent` | Runs Hermes with four team tools (search, compare, read, corpus) and evidence rules | Super 3.5 VL |
| `site` | Builds a static website and one compiled LaTeX document per scan | – |
| `evaluate` | Checks quotes against tool results and writes three success and three failure cases | – |

### 1. Super VL correction of the Parse text

After Parse 3.5, Super 3.5 VL reads each text block again: an enlarged crop of the block's box, together with the Parse text.
We measured the result against hand transcriptions of 30 blocks from 15 scans
([docs/evaluation/ocr-correction.md](docs/evaluation/ocr-correction.md)).

| Text | Character error rate | Word error rate | Blocks better than Parse |
| --- | --- | --- | --- |
| Parse 3.5 | 12.2% | 25.1% | – |
| Parse 3.5 + Super VL (block crop) | 1.8% | 3.0% | 28 of 29 |
| ... + dictionary long-s rule (used) | 1.8% | 2.9% | 28 of 29 |

- The character error rate falls 6.8 times.
- Reasoning off is better and about 12 times faster than reasoning on. The whole page instead of a block crop does not work.
- The correction also improves the later stages. With the same match rule, accepted matches rose from 53 to 80,
  and Britannica tokens outside the vocabulary fell from 18.8% to 10.6%.
- Example: the headword "WILLIN" became "WILLIAM", and NAXOS now reads "capital of the Isle of Naxos" instead of "capital of the lake of Naoxe".

### 2. Calibrated matching with the embedder and reranker

We labelled 60 entries by hand, with the model scores hidden, and calibrated the accept rule on them
([docs/evaluation/match-calibration.md](docs/evaluation/match-calibration.md)).

| Ranker | First candidate correct (43 labelled entries) |
| --- | --- |
| BM25 | 28% |
| Embedder cosine | 49% |
| Reranker logit | 65% |

| Accept rule | Precision | Recall | F1 |
| --- | --- | --- | --- |
| Headword and title rule | 0.71 | 0.47 | 0.56 |
| Reranker first candidate, margin ≥ 0.5, cosine ≥ 0.15 (cross-validated) | 0.62 | 0.56 | 0.59 |

- The full run accepted 86 of 201 searched entries with the model rule.
- The reranker found articles that the title rule missed. For example, COINAGE matches "Coining (mint)".
- It also rejected wrong title matches, such as NAXOS → "Naxos (Crete)".
- It still makes errors: it rejected HEAT → "Heat" because the margin to the second candidate was 0.15.

### 3. Hermes agent on the improved evidence

Hermes runs `nvidia/Nemotron-3.5-Super-VL` through Nebius Token Factory with the four team tools.
The latest run (`artifacts/agent/runs/2026-10-18T124947Z/`) completed all 8 questions, and 6 passed the automatic checks.
The other 2 gave the expected answer in words that the text rules do not detect.

- With the corrected text, the agent quotes readable sources. For NAXOS it quotes "capital of the Isle of Naxos, opposite the Isle of Paros" and places the town in the Cyclades, not in Crete.
- It questions weak matches: it reports that the accepted PHILOLOGY pair and the WILLIAM pair do not describe the same subject.
- When an entry has no accepted match (HEAT), it says that the comparison evidence is missing.
- [docs/evaluation/cases.json](docs/evaluation/cases.json) lists the three success cases and three failure cases from the saved runs.

### 4. Overall effect

| Measure | First run (Parse text, title rule) | Now (Super VL text, model rule) |
| --- | --- | --- |
| Entries | 241 | 249 |
| Matched pairs | 53 | 86 |
| Britannica tokens outside the vocabulary | 18.8% | 7.5% |
| Mean word-frequency cosine of the pairs | 0.14 | 0.24 |

The vocabulary and cosine numbers are proxies, not accuracy measurements.
The gold transcriptions and match labels come from one labeller (the coding agent) and have no second review.

## Infrastructure

Britannica scans enter your CPU workspace for ingestion and caching.
Your tools call the shared Parse and Wikipedia APIs and your team's GPU services.
Hermes runs in the CPU workspace and calls Super VL through Token Factory.

![Participant infrastructure and Britannica ingestion](docs/assets/nebius-participant-infrastructure.png)

[Full-size PNG](docs/assets/nebius-participant-infrastructure.png) · [Editable SVG](docs/assets/nebius-participant-infrastructure.svg)

## Start

Create your team's repository from this GitHub template.
Clone your repository.
Open a terminal in its root directory.

Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
Use Python 3.12.

```sh
uv sync --locked
cp .env.example .env
uv run nemotron-challenge doctor --offline
uv run nemotron-challenge stages
```

The offline check tests the starter setup. It does not complete the challenge.

Open this folder in your coding agent.
Ask it to read [AGENTS.md](AGENTS.md).
Choose your first milestone.

## Get the source scans

```sh
uv run nemotron-challenge data show
uv run nemotron-challenge data fetch
```

All teams use the same 100 scans and source checksums.
The first fetch downloads a pinned Parquet file of about 357 MiB.
The loader writes the selected scans to `data/raw/britannica`.
It leaves the source cache unchanged.

Use the shared [Wikipedia API](docs/wikipedia-api.md) to search the pinned English Wikipedia snapshot.
Teams do not need to download or build that index.

### Why Wikipedia is pre-indexed

The organizer has built a BM25 keyword index over 7,182,883 canonical English articles from a fixed snapshot.
This saves each team the download, storage, and index-building work for that corpus.
All teams search the same source revision.
Search makes no embedding or reasoning model calls.

Participants use it as follows:

1. Extract a Britannica entry with Parse 3.5.
2. Search terms from the entry to get candidate article IDs and excerpts.
3. Fetch candidate article text through the paginated article API.
4. Use Nemotron embeddings and reranking to assess candidates and decide whether a match is supported.
5. Cache the selected text and source metadata for comparisons and agent evidence.

The shared index supplies candidates, not verified Britannica matches.
Your team's LanceDB index holds its chosen evidence and vectors, separate from the shared keyword index.
Read the [API guide](docs/wikipedia-api.md) for client calls, pagination, and citation metadata.

### Multimodal matching concept

This illustration uses Wikipedia article text as a query to find Britannica page scans about the same subject.
Nemotron Embedder VL encodes the scans, with optional extracted text, into page vectors.
It encodes the article title and selected excerpt into a query vector.
Similarity search returns a shortlist of page IDs.
Nemotron Reranker VL then reads the query text with each original candidate page and ranks the results.

![Conceptual workflow from Wikipedia article text through Nemotron Embedder VL similarity search and Nemotron Reranker VL to ranked Britannica pages](docs/assets/nemotron-vl-matching.png)

[Full-size PNG](docs/assets/nemotron-vl-matching.png)

The challenge starts from Britannica entries and searches Wikipedia through the shared API.
The diagram reverses that direction to explain the models' text and image inputs.
Your team chooses its matching method and checks each selected association against both sources.
The page examples are illustrative. Relevance scores do not establish factual agreement or identical coverage.
See the [Embed VL model card](https://huggingface.co/nvidia/llama-nemotron-embed-vl-1b-v2) and [Rerank VL model card](https://huggingface.co/nvidia/llama-nemotron-rerank-vl-1b-v2) for the model contracts.

## Set up the models

The organizer supplies Parse 3.5 and the Wikipedia API.
Deploy the embedder and reranker in your Nebius AI Cloud project.
Use the [Docker recipe](docs/model-service.md) or an organizer-provided image.

Create a separate Nebius Token Factory account for Super 3.5 VL.
Set your URLs and keys in `.env`.
Keep that file out of Git.
Use the [Hermes guide](docs/hermes.md) to install the tool stub and model settings.

```sh
uv run nemotron-challenge doctor --live
```

The live check tests service access and model catalogs.
Read its output for missing settings and test limits.

## Build your solution

Follow the [milestones](docs/milestones.md).
The stage entry points contain TODOs and stop with a task message until your team implements them.

```sh
uv run nemotron-challenge run extract
```

Read the [challenge brief](docs/challenge.md) for the required models and deliverables.
Use the [submission template](templates/submission.md) to record your results.
Submit a video of 3 to 5 minutes and your solution repository.

### Topic comparison with BERTopic

The illustration shows one method for comparing Britannica entries with selected Wikipedia articles.
It uses Nemotron embeddings for both sources, then UMAP, HDBSCAN, term counts, and c-TF-IDF.
The optional Super VL stage generates topic labels and summaries without training model weights.
Choose your comparison method with your team.

![BERTopic with Nemotron embeddings and optional Super VL topic refinement](docs/assets/bertopic-nemotron-implementation.png)

[Full-size PNG](docs/assets/bertopic-nemotron-implementation.png) · [Editable SVG](docs/assets/bertopic-nemotron-implementation.svg)

## Check the foundation

```sh
uv run pytest
```

These tests cover the starter infrastructure and data contracts.
Replace a stage's unfinished-state test when you implement that stage.
Your team must test retrieval quality, citation support, and agent behavior.
Record three successes and three failures from your own runs.

## Licenses

Original starter code uses [MIT](LICENSE).
Data and model weights retain their source licenses.
Read [ATTRIBUTION.md](ATTRIBUTION.md) before you share source material or model artifacts.
