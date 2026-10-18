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
- its logit is at least -10 (no effective bar),
- no title-similarity test (threshold 0).

The grid search over logit, margin, cosine, and title similarity chose these values for the best F1 on all 60 entries.
The grid includes the rule from the first GPU run on `main` (logit ≥ -6.0 and title similarity ≥ 0.75). A title test did not raise F1.

## Method update: LLM terms and F2 fitting

The queries changed. The match stage now also sends the Super VL title guess and its terms as a fourth
BM25 query. That query returns pages the labeller never saw, so the scoring and the fit changed:

- Before the new run, `calibrate.snapshot_judged` stores the candidate page IDs of each labelled entry
  in `docs/evaluation/match_judged.json`. That file keeps the set of pages the labeller saw.
- An accepted page that is not in the accept list counts as a false positive only when the labeller saw
  it. A page outside the judged set counts as `unjudged` and stays out of the precision count.
- The grid search now fits the thresholds for the best F2, so recall weighs twice precision. It reports
  the unjudged accepts with their titles for a person to label.
- `match_thresholds.json` records the objective, the unjudged accepts, and the label coverage: the share
  of labelled accept pages that the new candidate list still contains, and the count of new candidates
  per entry outside the judged set.

To re-run: take the judged snapshot once, run the match stage, then run the calibration.

```sh
uv run python -c "from pathlib import Path; from nemotron_challenge.calibrate import snapshot_judged; snapshot_judged(Path('artifacts'))"
uv run nemotron-challenge run match
uv run python -c "from pathlib import Path; from nemotron_challenge.calibrate import run; run(Path('artifacts'))"
```

## Results

The results below come from the previous run: the F1 fit on the old candidate set, before the LLM terms
query existed. New results follow the next run.

| Rule | Accepted | Correct | Wrong | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- |
| Lexical title rule (no fitting) | 28 | 20 | 8 | 0.71 | 0.47 | 0.56 |
| First GPU-run rule: logit ≥ -6.0, title ≥ 0.75 (not fitted on these labels) | 24 | 19 | 5 | 0.79 | 0.44 | 0.57 |
| Model rule, two-fold cross-validation | 39 | 24 | 15 | 0.62 | 0.56 | **0.59** |
| Model rule, fitted on all 60 (optimistic) | 28 | 23 | 5 | 0.82 | 0.53 | 0.65 |

- Cross-validation fits the thresholds on one half and tests them on the other half. That row is the honest estimate.
- The model rule finds more correct pairs than the lexical rule and the first GPU-run rule, with lower precision.
- On the full run (201 entries), the calibrated rule accepts 86 entries and the first GPU-run rule 73.
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

- The labels cover only the BM25 candidates of the old run. An article that BM25 did not return cannot be found or labelled.
- The labels judge only the old candidate set. An unjudged accept can be right or wrong; a person must label it before we know the real precision.
- F2 favours recall, so the new rule accepts more entries and will also accept more wrong ones.
- The margin rule rejects a correct article when a second candidate scores close to it (HEAT).
- One labeller; no second review.
