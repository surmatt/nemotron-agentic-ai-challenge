# Match calibration with the Nemotron embedder and reranker

The match stage gets up to 32 BM25 candidates for each Britannica entry.
`nvidia/llama-nemotron-embed-vl-1b-v2` gives a cosine between the entry text and each candidate (title and excerpt).
`nvidia/llama-nemotron-rerank-vl-1b-v2` gives a raw logit for each pair and ranks the candidates.
This file reports how the team chose the accept rule and how well it works on hand labels.

Code: `src/nemotron_challenge/calibrate.py` and `match.py`. Labels: `docs/evaluation/match_labels.json`.
Thresholds: `docs/evaluation/match_thresholds.json`. Saved run: `artifacts/match/calibration.json`.

## Labels

- 60 of the 200 entries that the models scored, chosen with seed 20261019.
- The labeller read the Super VL corrected entry text and the candidates in BM25 order. Model scores were hidden.
- Each label lists every candidate that describes the subject of the entry. 43 entries have at least one; 17 have none.
- One labeller (the coding agent) made the labels. Nobody reviewed them.

## How the models rank the candidates

Share of the 43 labelled entries where the first candidate is correct:

| Ranker | Correct first candidate |
| --- | --- |
| BM25 rank | 12 of 43 (28%) |
| Embedder cosine | 21 of 43 (49%) |
| Reranker logit | 28 of 43 (65%) |

The reranker ranks best. Its raw logits are low even for correct pairs (median about -2.8), so a fixed logit bar of 0 rejects almost everything.

## Accept rule

Accept the reranker's first candidate when:

- its margin to the second candidate is at least **0.5**,
- its embedder cosine is at least **0.15**,
- its logit is at least -10 (no effective bar).

The grid search (logit, margin, cosine) chose these values for the best F1 on all 60 entries.

## Results

| Rule | Accepted | Correct | Wrong | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- |
| Lexical title rule (no fitting) | 28 | 20 | 8 | 0.71 | 0.47 | 0.56 |
| Model rule, two-fold cross-validation | 39 | 24 | 15 | 0.62 | 0.56 | **0.59** |
| Model rule, fitted on all 60 (optimistic) | 28 | 23 | 5 | 0.82 | 0.53 | 0.65 |

- Cross-validation fits the thresholds on one half and tests them on the other half. That row is the honest estimate.
- The model rule finds more correct pairs than the lexical rule, with lower precision.
- 30 entries per half is a small sample. The two folds chose different thresholds: (margin 0.0, cosine 0.2) and (margin 0.5, cosine 0.0).

## Examples from the full run

| Entry | Lexical rule | Model rule |
| --- | --- | --- |
| COINAGE (E0100) | rejected (no title match) | **Coining (mint)**, the article on making coins |
| NAXOS (E0103) | Naxos (Crete), wrong place | rejected (margin 0.12) |
| HEAT (E0090) | Heat | rejected: margin 0.15 < 0.5, a **false negative** |
| WILLIAM (E0013) | rejected | List of people with given name William (partial) |

## Full run

- 201 entries searched, 86 accepted, 115 rejected, 0 errors.
- One entry (E0182, a rainfall table) passed the 512-token query limit of the embedder. The stage then shortened the query to 700 characters.

## Limits

- The labels cover only the BM25 candidates. An article that BM25 did not return cannot be found or labelled.
- The margin rule rejects a correct article when a second candidate scores close to it (HEAT).
- One labeller; no second review.
