# Nemotron Agentic AI Challenge

We compare historical Britannica scans with Wikipedia and use a Hermes agent to answer comparison questions with source evidence.

Our solution adds OCR correction, article matching, vocabulary analysis, summaries of differences, semantic search, and a visual workbench to the challenge starter.
The outputs include a static website, compiled LaTeX documents, saved model replies, and three success and three failure case studies.

## Latest end-to-end results

The latest recorded end-to-end run is **e2e4**, on 2026-10-18 at commit `61e8d29`.
It ran in `artifacts-e2e4/` in about 12 minutes.
All eight stages in that revision exited with code 0.
Before the run, 169 tests passed and the live service check passed for Wikipedia, Parse, retrieval, and Super VL.
See [the run report](docs/evaluation/e2e-runs.md) for thresholds, failures, and the match-output checksum.

| Result | e2e4 | Previous run, e2e3 |
| --- | --- | --- |
| Scans parsed | 98 of 100 | 98 of 100 |
| Text blocks corrected | 1,147 of 1,148 | 1,146 of 1,148 |
| Entries in the site | 250 | 248 |
| Wikipedia matches | 176 accepted, 25 rejected, 201 searched | 86 accepted, 113 rejected, 199 searched |
| Compared pairs / distinct Wikipedia articles | 176 / 171 | 86 / 84 |
| Indexed Britannica / Wikipedia passages | 687 / 1,948 | 685 / 900 |
| Hermes questions completed / automatic passes | 8 of 8 / 5 | 8 of 8 / 6 |
| Scan pages / compiled PDFs | 98 / 98, no LaTeX failures | 98 / 98, no LaTeX failures |
| Agent runs checked / case studies generated | 8 / 0 | 8 / 0 |

The current matching method adds Super VL search terms and removes the score-margin gate.
Accepted matches rose from 86 to 176, but nobody has measured the precision of e2e4.
More accepted pairs do not prove better matching.
Automatic agent checks are text rules, not a factual-accuracy score.

Eight failures were retained: two incomplete Parse replies, one incomplete OCR-correction reply, and five incomplete search-term replies.
The pipeline continued without those results.
The isolated run generated no case studies because the six selected cases refer to earlier runs in `artifacts/`.
Those [saved case studies](#case-studies) remain separate evidence.

The `summarize` stage was added after e2e4.
The results above do not measure that stage or the current nine-stage pipeline.

## Team solution and results

Our pipeline has nine stages. Run each one with `uv run nemotron-challenge run <stage>`.
[docs/team-pipeline.md](docs/team-pipeline.md) describes the method of each stage.

| Stage | What it does | Models |
| --- | --- | --- |
| `extract` | Parses each scan, keeps the raw reply, removes page furniture, and splits entries at headwords | Parse 3.5 |
| `correct` | Corrects the Parse text of each block from an enlarged crop of the scan | Super 3.5 VL |
| `match` | Gets BM25 candidates (headword, cleaned frequency keywords, Super VL terms), ranks them with the reranker, and accepts by calibrated thresholds | Super 3.5 VL, Embed VL, Rerank VL |
| `compare` | Compares word frequencies with log-odds and cites a snippet from both sources | – |
| `index` | Embeds Britannica and Wikipedia passages and stores them with citations in LanceDB | Embed VL |
| `summarize` | Lists the key differences of each pair with one quote per side, and checks each quote against the source | Super 3.5 VL, Embed VL |
| `agent` | Runs Hermes with five team tools (search, semantic search, compare, read, corpus) and evidence rules | Super 3.5 VL |
| `site` | Builds a static website and one compiled LaTeX document per scan | – |
| `evaluate` | Checks quotes against tool results and writes the selected cases when their saved runs are present | – |

The vocabulary comparison uses accepted pairs, not all extracted entries.
It compares word frequencies with log-odds z-scores and an informative Dirichlet prior.
Corpus counts include each matched Wikipedia article once.
Tokenization keeps lowercase letter sequences of at least three letters and removes stop words.
Britannica abbreviation, long-s, and historical-spelling changes are logged.
Words outside the reference vocabulary are counted as unverified and excluded from the comparison term lists.
The reference vocabulary combines cached Wikipedia text with the system word list when available.
Source snippets retain the source wording; the generated difference summaries are labelled separately.

### 1. Super VL correction of the Parse text

We tried upscaling scans and cropping them into columns along a vertical line. Neither improved extraction quality.

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

We labelled 60 entries by hand, with the model scores hidden, and measured the previous accept rule
([docs/evaluation/match-calibration.md](docs/evaluation/match-calibration.md)).
The current rule takes the top reranked page when its logit, cosine, and title similarity pass their
thresholds. It does not require a gap to the second candidate. Future calibration fits for F2.
The results below describe the previous rule, which used a margin threshold.

| Ranker | First candidate correct (43 labelled entries) |
| --- | --- |
| BM25 | 28% |
| Embedder cosine | 49% |
| Reranker logit | 65% |

| Accept rule | Precision | Recall | F1 |
| --- | --- | --- | --- |
| Headword and title rule | 0.71 | 0.47 | 0.56 |
| Reranker first candidate, logit ≥ -6, title ≥ 0.75 (first GPU run) | 0.79 | 0.44 | 0.57 |
| Reranker first candidate, margin ≥ 0.5, cosine ≥ 0.15 (cross-validated) | 0.62 | 0.56 | 0.59 |

- The earlier saved run in `artifacts/` accepted 86 of 201 searched entries with the margin-based rule.
- The reranker found articles that the title rule missed. For example, COINAGE matches "Coining (mint)".
- It also rejected wrong title matches, such as NAXOS → "Naxos (Crete)".
- The previous rule rejected HEAT → "Heat" because the margin to the second candidate was 0.15.
  The current rule removes that condition. These results do not measure the current rule.

### 3. LanceDB passage index and semantic search

The `index` stage stores Embed VL passage vectors with their citations in LanceDB.
The earlier saved run in `artifacts/` embedded 692 Britannica passages and 856 Wikipedia passages from 84 accepted articles in about 40 seconds.
The latest e2e4 run indexed 687 Britannica passages and 1,948 Wikipedia passages from 171 articles.
The Hermes tool `challenge_semantic_search` searches this index by meaning.

- Word search could not find the entry with the OCR headword "PHILLOOGY". Semantic search for "philology, the study of languages" returns that entry (E0021).
- "how coins were struck with dies and a hammer" returns the Wikipedia article "Coining (mint)" and the Britannica entry COINAGE.
- Each stage now replaces its own provenance records. The old runs left 154 match records for 86 current matches; these are gone.
- In agent run `2026-10-18T132500Z` (q06), Hermes called `challenge_semantic_search` after word search found no "locomotive" entry.
  It got Wikipedia passages on early steam locomotives and the Britannica STEAM-ENGINE entry, and reported that Britannica has no locomotive entry.
- The first full agent run with the tool (`2026-10-18T131943Z`) shows a failure: the tool returned an error, because the Hermes environment variables (`PYTHON*`, `VIRTUAL_ENV`) reached the project Python. The plugin now removes them and reports the exit code and last error line.

### 4. Hermes agent on the improved evidence

Hermes runs `nvidia/Nemotron-3.5-Super-VL` through Nebius Token Factory with five team tools.
In e2e4, all 8 questions completed and 5 passed the automatic checks.
The HEAT question passed in e2e3 but failed the e2e4 automatic check.
The quote checker also flagged the e2e4 PHILOLOGY answer.
Both need source review before classification.

An earlier run (`artifacts/agent/runs/2026-10-18T124947Z/`) completed all 8 questions and passed 6 automatic checks.
The examples below describe that earlier evidence, not e2e4:

- With the corrected text, the agent quotes readable sources. For NAXOS it quotes "capital of the Isle of Naxos, opposite the Isle of Paros" and places the town in the Cyclades, not in Crete.
- It questions weak matches: it reports that the accepted PHILOLOGY pair and the WILLIAM pair do not describe the same subject.
- When an entry has no accepted match (HEAT), it says that the comparison evidence is missing.
- [docs/evaluation/cases.json](docs/evaluation/cases.json) lists the three success cases and three failure cases from the saved runs.

### 5. Summary of differences

We added `summarize` after word-frequency comparison.
Super 3.5 VL reads each accepted pair and returns a subject-alignment judgement, a short overview, and up to five differences in facts, explanations, scope, or emphasis.
Each difference requests one exact quote from each source.

- The model reads the corrected Britannica entry and the Wikipedia article.
- For articles longer than 12,000 characters, Embed VL selects relevant passages. Stored LanceDB vectors are reused. Without retrieval, the stage uses the first passages and labels that fallback.
- The code checks each quote against its source text and records offsets and Wikipedia passage IDs.
- `quotes_found` means both quotes occur in the sources. It does not prove that the quotes support the claims. Claims, the overview, and the subject judgement remain model inference.
- Raw replies, prompts, and passage selections stay separate from derived summaries. Failed replies are retained and produce no invented summary.

Run `uv run nemotron-challenge run summarize` after `compare` and `index`.
Corpus outputs go to `artifacts/summarize/summaries.jsonl`, `summary.json`, and `raw/`.
The workbench shows the summary and both quote checks in the Comparison tab.
See [the stage method and limits](docs/team-pipeline.md) for details.
The latest recorded end-to-end run predates this addition, so it supplies no summary-stage quality result.

### 6. Earlier baseline comparison

These measurements compare the first run with the earlier margin-based model run saved in `artifacts/`, not e2e4.

| Measure | First run (Parse text, title rule) | Earlier improved run (Super VL text, margin-based rule) |
| --- | --- | --- |
| Entries | 241 | 249 |
| Matched pairs | 53 | 86 |
| Britannica tokens outside the vocabulary | 18.8% | 7.5% |
| Mean word-frequency cosine of the pairs | 0.14 | 0.24 |

The vocabulary and cosine numbers are proxies, not accuracy measurements.
The gold transcriptions and match labels come from one labeller (the coding agent) and have no second review.

## Submission evidence

The [submission template](templates/submission.md) asks for reproduction steps, model and source revisions, results, case studies, and limits.
The [case-study template](templates/case-study.md) asks for the question, saved run, code revision, source excerpts, and the reason for the classification.
The [LaTeX template](templates/page.tex) separates historical text from its source record.

The repository includes these deliverables from earlier saved runs:

| Deliverable | Evidence |
| --- | --- |
| Static website and compiled documents | [Site](artifacts/site/index.html), [LaTeX sources and PDFs](artifacts/site/latex/), [build summary](artifacts/site/summary.json) |
| Comparison analysis | [Pair records](artifacts/compare/pairs.jsonl), [corpus counts](artifacts/compare/corpus.json), [plots](artifacts/compare/plots/), [normalisation log](artifacts/compare/normalisation_log.jsonl) |
| Source and model records | [Raw Parse replies](artifacts/extract/raw/), [OCR corrections](artifacts/correct/), [Wikipedia candidates and articles](artifacts/match/), [Hermes runs](artifacts/agent/runs/) |
| Evaluation | [Selected cases and repairs](docs/evaluation/cases.json), [evaluation summary](artifacts/evaluate/summary.json), [latest end-to-end report](docs/evaluation/e2e-runs.md) |

These files are not the e2e4 outputs.
The `artifacts-e2e*/` work directories are ignored by Git and exist only on the machine that ran them.
The submission template still needs team details, the final repository commit, the video URL, and the hosted website URL.

### Case studies

These cases describe specific earlier saved runs.
Failed attempts and later repairs have separate run records.

| Classification | Case | What it shows |
| --- | --- | --- |
| Success | [HEAT comparison](artifacts/evaluate/cases/S1-heat.md) | Reads both sources and cites evidence for different accounts of heat |
| Success | [WILLIN wrong match](artifacts/evaluate/cases/S2-willin-wrong-match.md) | Rejects a wrong Wikipedia association instead of trusting the matcher |
| Success | [Missing locomotive entry](artifacts/evaluate/cases/S3-locomotive-missing.md) | Reports missing evidence without filling the gap from memory |
| Failure | [PHILOLOGY false absence](artifacts/evaluate/cases/F1-philology-false-absence.md) | OCR prevents discovery, and the agent claims the entry is absent |
| Failure | ["Brit." interpretation](artifacts/evaluate/cases/F2-corpus-brit-inference.md) | Explains a printed abbreviation as an OCR fragment without reading the source |
| Failure | [Unsupported edition](artifacts/evaluate/cases/F3-heat-no-rules-edition.md) | States an edition that no tool result supports |

### Known limits

- Two of the 100 scans did not yield complete Parse replies. The website and PDFs cover 98 scans.
- The small OCR gold set excludes tables, formulas, pictures, and headers. Gold text and match labels have no second review.
- The previous calibration scores do not measure the e2e4 candidate set or no-margin rule. Current match precision remains unknown.
- Automatic agent and quote checks need human review. The e2e4 HEAT and PHILOLOGY answers remain open review items.
- Summary quote checks establish text occurrence, not factual support. Selected passages cannot prove that a whole source omits a topic.
- A zero exit code does not mean complete coverage, correct matches, or six reproduced case studies. Check stage summaries and failure records.

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
To repeat the stage sequence recorded for e2e4, use its tested revision `61e8d29` and omit `summarize`.
Model output and entry counts can vary between runs.

Inspect each stage's `summary.json` and `runs/failures.jsonl`.
In a fresh work directory, `evaluate` can check the new agent runs but will not reproduce the six selected cases unless their original run records are present.
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

The retrieval recipe pins Python 3.11, PyTorch 2.8.0, CUDA 12.8, and Transformers 4.56.2.
Its Nebius Serverless command uses one RTX PRO 6000 GPU.
See [the service recipe](docs/model-service.md) for the image digest, package hashes, and runtime checks.
Correction and summarization use temperature 0 with reasoning off.
The e2e4 match thresholds were logit >= -10.0, cosine >= 0.15, and title similarity >= 0.0, with no margin gate.

The workspace uses Python 3.12; application versions are pinned in `uv.lock`.
The e2e4 report records 169 passing tests but does not record the exact Python patch version or a full installed-package inventory.
Record those details with the final submission run rather than infer them from another environment.
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

### Topic comparison with BERTopic

The illustration shows an optional method for comparing Britannica entries with selected Wikipedia articles.
It uses Nemotron embeddings for both sources, then UMAP, HDBSCAN, term counts, and c-TF-IDF.
The optional Super VL stage generates topic labels and summaries without training model weights.
Our implemented comparison uses word-frequency log-odds and the difference summaries described above, not BERTopic.

![BERTopic with Nemotron embeddings and optional Super VL topic refinement](docs/assets/bertopic-nemotron-implementation.png)

[Full-size PNG](docs/assets/bertopic-nemotron-implementation.png) · [Editable SVG](docs/assets/bertopic-nemotron-implementation.svg)

## Visual workbench

The workbench shows the pipeline on one scan at a time.
Upload a scan and run the six steps: extract, correct, match, compare, summarize, and document.
Each view shows the scan with block boxes, the Super VL corrections, the Wikipedia candidates with their scores, the term comparison, the summary of differences with quote checks, the LaTeX document, and the raw model replies.

You need Node.js 20.19 or later.
For PDFs, install `tectonic` (`brew install tectonic` on macOS). Without it, the document step writes `.tex` files only.
Start the backend and the frontend with one command.

```sh
make run
```

Open <http://127.0.0.1:5173>.
The command installs the Python and npm packages if necessary.
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
Use `--work-dir` to change the artifacts folder. The default is `artifacts`.

- **Workbench tab:** drop a JPEG or PNG scan, then click **Run all steps** or run one step at a time. The server keeps each upload in `artifacts/ui/uploads/<id>/`.
- **Corpus tab:** browse the 100 pinned scans with the saved stage outputs from `artifacts/`. Click **Run live in workbench** to copy a scan into the workbench and run the steps on it.
- **Re-run a stage:** click **Re-run** on a stage card. The stage runs again, then each later stage that ran before. The `+N` badge shows the number of other stages that run with it. Hold the pointer on the button to see their names. Earlier outputs move to `history/<time>/` in the upload folder.
- **Apply a new match rule:** in an upload's Matching tab, click **Apply current rule (reuse scores)**. This updates the saved decisions from the existing candidate scores without search or model calls. It fetches full text for newly accepted Wikipedia articles and rebuilds later outputs that ran. Changed entry text requires a full Match re-run.
- **Re-run on a corpus scan:** the workbench copies the scan and reuses the saved Parse and Super VL replies of the corpus run. Then it runs the chosen stage and the later stages. Match has no per-scan saved output, so a compare re-run also runs match. The corpus artifacts stay unchanged.
- **Check services:** runs the live check on Parse, Super VL, the retrieval service, and the Wikipedia API.
- **Summary of differences:** step V calls Super VL and shows the generated overview, subject judgement, differences, and source quotes in the Comparison tab. Each quote has a found/not-found check. Claims remain labelled as inference.
- **LaTeX document tab:** step VI writes one LaTeX document for the scan with the code in `site.py`, and tectonic compiles it. The tab shows the PDF next to the `.tex` source. On a corpus scan, the tab shows the document from the last site build.
- **Static site:** on the overview, click **Build site** to run the site stage on the saved corpus artifacts. The same command is `uv run nemotron-challenge run site`. Then click **Open static site**. The server serves it at `/site/index.html`. The first build downloads the LaTeX packages for tectonic, so it takes longer.

The live steps read the service URLs and keys from `.env`.
Extract calls Parse. Correct calls Super VL. Match calls Super VL, the Wikipedia API, and the retrieval service.
Summarize calls Super VL and uses the retrieval service to rank passages of long Wikipedia articles.
Compare and document run locally.
If `RETRIEVAL_BASE_URL` is not set or does not answer, match uses lexical mode and the step summary says so.
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
Uploads stay in the container file system and are lost when the endpoint restarts.

Build the image from the repository root.

```sh
docker buildx build --platform linux/amd64 --load -f infra/workbench/Dockerfile -t nemotron-workbench:local .
```

Use `--build-arg ARTIFACTS_DIR=<folder>` to ship a different saved run.
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

Tests cover data contracts, clients, stage behavior, calibration, passage search, summaries, and workbench reruns.
Fixture tests do not prove OCR accuracy, retrieval quality, or factual support.
The measured OCR and earlier matching results are linked above.
The [end-to-end report](docs/evaluation/e2e-runs.md) records the checks made before e2e4.
It predates the summary stage, so its 169-test count is not a current-suite result.

## Licenses

Original starter code uses [MIT](LICENSE).
Data and model weights retain their source licenses.
Read [ATTRIBUTION.md](ATTRIBUTION.md) before you share source material or model artifacts.
