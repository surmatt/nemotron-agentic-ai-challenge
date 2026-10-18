# Team pipeline

This file describes the methods that the team chose for each stage.
Each stage module in `src/nemotron_challenge/` explains its method at the top of the file.

## Run all stages

```sh
uv sync --locked
uv run nemotron-challenge data fetch
uv run nemotron-challenge run extract
uv run nemotron-challenge run match
uv run nemotron-challenge run compare
uv run nemotron-challenge run agent
uv run nemotron-challenge run site
uv run nemotron-challenge run evaluate
uv run nemotron-challenge stages
```

Each stage writes to `artifacts/<stage>/` and writes `summary.json` last.
Each stage reads the files of the earlier stages.
Failed model calls go to `artifacts/runs/failures.jsonl` with their error details.

The agent stage needs Hermes Agent. Read [hermes.md](hermes.md).
The site stage compiles LaTeX with `tectonic` when it is installed. Without it, the stage writes `.tex` files only.

## Methods

| Stage | Module | Method |
| --- | --- | --- |
| Extract | `extract.py` | Parse 3.5 per scan. Raw replies stay unchanged in `extract/raw/`. Page headers, footers, and page numbers are removed. A capitalised headword starts an entry. Continuations join only across consecutive rows of one volume. |
| Match | `match.py` | Two BM25 searches per entry (headword, then headword with keywords). With the retrieval service: Nemotron embedder cosine and reranker logits decide. Without it: a headword and title rule, labelled `provisional_lexical`. |
| Compare | `compare.py` | Word frequencies. Long s and historical spelling are normalised and logged. Log-odds z-scores with an informative Dirichlet prior. Each distinctive term has one source snippet per side. |
| Agent | `agent.py`, `integrations/hermes/` | Hermes with Super 3.5 VL and four tools: search, compare, read, corpus. The evidence rules and questions are in `integrations/hermes/questions.json`. |
| Site | `site.py` | Static HTML and one LaTeX document per scan. Source text and generated analysis have separate, labelled sections. |
| Evaluate | `evaluate.py`, `evaluation/cases.json` | The team classifies six saved runs by hand. The stage checks quotes against the tool results and writes the case studies. |

## Open the site

```sh
uv run python -m http.server 8791 --bind 127.0.0.1 --directory artifacts/site
```

Open `http://127.0.0.1:8791/` in a browser.

## Known limits

- The first full run used the lexical match rule. The embedder and reranker were not available.
  Run `match` and the later stages again after you set `RETRIEVAL_BASE_URL`.
- The first model run used `RERANK_ACCEPT = 0.0` and `COSINE_ACCEPT = 0.30` and accepted 1 of 188 entries.
  Its output is in `artifacts/runs/match-run1-uncalibrated/`.
  The current rule accepts the reranker top-1 if its logit is at least -6.0 and its title similarity to the headword is at least 0.75.
  Check `RERANK_ACCEPT` and `MODEL_TITLE_ACCEPT` again on hand-checked pairs.
- Entries without a headword cannot pass the model rule.
- `artifacts/evaluate/summary.json` lists the other known limits.
