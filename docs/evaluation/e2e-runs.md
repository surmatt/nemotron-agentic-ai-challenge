# End-to-end runs

This file records full pipeline runs in a new work dir.
Each run uses all eight stages in order: extract, correct, match, compare, index, agent, site, evaluate.

The `artifacts-e2e*/` folders are in `.gitignore`. They exist only on the machine that made the run.
The index stage writes its tables to `data/team.lancedb` with the work dir in the table name, so a run does not change `artifacts/`.

## How to run

```sh
for s in extract correct match compare index agent site evaluate; do
  uv run --locked nemotron-challenge run $s --work-dir artifacts-e2eN || break
done
```

Before the run, do `uv run --locked pytest` and `uv run nemotron-challenge doctor --live`.

## e2e4: main at `61e8d29`, 2026-10-18

- Code: `main` at `61e8d29` (merge of PR #8, match-llm-terms: Super VL search terms, no margin gate).
- Work dir: `artifacts-e2e4/`.
- Time: 15:35 to 15:46 UTC, about 12 minutes. All eight stages exited with code 0.
- Before the run: 169 tests passed. `doctor --live` reported wikipedia, parse, retrieval, and super as ok.
- `match/matches.jsonl` SHA-256: `9ed1d156144ff66a7b1fdcf59264c61ba6889f4f0379df31187a9fcbff482683`.

| Stage | e2e4 | e2e3 (13:52 UTC, before PR #8) |
| --- | --- | --- |
| extract | 98 of 100 scans parsed, 241 entries | same |
| correct | 1147 of 1148 blocks corrected, 1 failed | 1146 of 1148, 2 failed |
| match | 201 searched, **176 accepted**, 25 rejected | 199 searched, 86 accepted, 113 rejected |
| compare | 176 pairs | 86 pairs |
| index | 687 Britannica and 1948 Wikipedia passages, 171 articles | 685 and 900, 84 articles |
| agent | 8 of 8 completed, 5 automatic passes | 8 of 8 completed, 6 automatic passes |
| site | 98 scan pages, 250 entry pages, 98 PDFs, 0 LaTeX failures | 98, 248, 98, 0 |
| evaluate | 8 runs checked, 0 cases | 8 runs checked, 0 cases |

### Match thresholds in this run

`rerank_logit` -10.0, `cosine` 0.15, `title_similarity` 0.0 (from `docs/evaluation/match_thresholds.json`).
Super VL terms: 196 ok, 5 failed.

### Failures

`artifacts-e2e4/runs/failures.jsonl` has 8 records. All are model replies cut at the token limit:

| Stage | Count | Error |
| --- | --- | --- |
| match_terms | 5 | `ProtocolError`: chat response is incomplete (E0144, E0209, E0234, and 2 more) |
| extract | 2 | `ProtocolError`: chat response is incomplete |
| correct | 1 | `ValueError`: incomplete Super VL reply, `finish_reason=length` |

The pipeline continued without these results.

### Open points

- The number of accepted matches doubled. Nobody has measured the precision of this run.
  Inference: the low thresholds (title similarity 0.0, no margin) accept more wrong pages. Check a sample against `match_labels.json`.
- Agent question `q01-heat` passed in e2e3 and failed the automatic check in e2e4. Read the answer before you classify it.
- The quote checker flagged `2026-10-18T154454Z/q05-philology`. Read the quote to decide if it is a checker false alarm.
- Evaluate found 0 cases. The six selected cases point to runs in `artifacts/`, not to this work dir. This is the same as in e2e3.
