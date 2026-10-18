# Case study

Case ID: F2-corpus-brit-inference
Classification: failure
Run record: `artifacts/agent/runs/2026-10-18T114003Z/q04-corpus.jsonl` (run `2026-10-18T114003Z`, question `q04-corpus`, Hermes session `20261018_134119_7b1923`)
Code revision: `6a8987c49d078fc8c2d7c60c008498011e2f6ed0 + uncommitted changes`

## Question

Across all matched pairs, which words most distinguish the Britannica vocabulary from the Wikipedia vocabulary? Give counts.

## Evidence

- Model: `nvidia/Nemotron-3.5-Super-VL` (expected `nvidia/Nemotron-3.5-Super-VL`: True)
- Tool calls, in order: tool_describe, challenge_corpus
- Britannica entry IDs cited: none
- Wikipedia revision IDs cited: none
- Cited IDs absent from tool results: none
- Quoted passages checked against the tool results of this run:
- No quoted passages.

## Result

The agent reported the corpus terms and counts correctly, but explained the top term "brit" as "almost certainly an OCR fragment" of British or Britannia. All 33 counted occurrences are the printed abbreviation "Brit." in entry E0002 (WEIGHTS AND MEASURES), for example "27/430 Brit. cubic inches". The agent did not read the source before it made the claim.

Limits: The agent labelled the explanation as an interpretation. The term list itself is correct. The comparison stage should expand or exclude the abbreviation.
Repair: Expand abbreviations such as Brit. in the compare stage, and require a challenge_read call before the agent explains a term.

Automatic check: pass. The automatic check uses text rules. This classification comes from a manual review of the answer and the sources.

<details><summary>Agent answer</summary>

Source: challenge_corpus (corpus-level comparison of all matched pairs). Corpus: 57 Britannica documents, 55 Wikipedia documents; every match was made by the provisional_lexical method; frequency cosine 0.5254; 19.25% of Britannica tokens were unverified (noisy OCR), so OCR errors limit these counts. Counts are corpus aggregates over only entries with an accepted match; there are no per-entry page IDs at this level.

Words whose frequency most distinguishes the Britannica vocabulary from the Wikipedia vocabulary (distinctive_britannica, ranked by z-score):

| term | z | count_britannica | count_wikipedia |
|------|-----|------------------|-----------------|
| brit | 5.531 | 33 | 0 |
| placed | 3.699 | 23 | 10 |
| native | 3.52 | 24 | 14 |
| eyes | 3.44 | 18 | 6 |
| marked | 3.359 | 15 | 3 |
| cells | 3.192 | 12 | 1 |
| afterwards | 3.057 | 12 | 2 |
| fine | 3.038 | 17 | 9 |
| piece | 2.961 | 13 | 4 |
| principal | 2.929 | 12 | 3 |
| force | 2.904 | 21 | 18 |
| abdomen | 2.889 | 10 | 1 |

Interpretation: "brit" is the strongest discriminator (33 in Britannica, 0 in Wikipedia), but it is almost certainly an OCR fragment (e.g., a truncated "British"/"Britannia") rather than a standalone word — treat it as an artifact of noisy OCR, not a genuine lexical difference. The next strongest genuine discriminators are "placed" (23 vs 10), "native" (24 vs 14), and "eyes" (18 vs 6), consistent with Britannica entries containing more physical/descriptive and natural-history phrasing.

For contrast, the words most distinctive of Wikipedia are: esarhaddon (1 vs 168), energy (0 vs 144), heat (15 vs 296), huguenot (0 vs 132), buxton (2 vs 145), huguenots (1 vs 130), political (1 vs 127), comitas (0 vs 102), century (2 vs 117), aquinas (0 vs 92), work (5 vs 147), known (2 vs 113).

</details>

## Repaired run

The classification above describes the failed run. This section records a later run after a repair.

Run record: `artifacts/agent/runs/2026-10-18T115609Z/q04-corpus.jsonl` (run `2026-10-18T115609Z`, question `q04-corpus`, Hermes session `20261018_135710_32d985`)
Repair outcome: fixed

- Tool calls, in order: tool_describe, challenge_corpus
- Britannica entry IDs cited: none
- Wikipedia revision IDs cited: none
- Cited IDs absent from tool results: none
- Automatic check: pass
- Quoted passages checked against the tool results of this run:
- No quoted passages.

Repair: compare.py expands the printed abbreviation "Brit." (and the OCR form "Brit;") to "British" before counting. 30 expansions are logged in compare/normalisation_log.jsonl. "brit" is no longer a corpus term. "british" counts 39 in Britannica and 49 in Wikipedia. The agent reports the term table from challenge_corpus and makes no claim about OCR fragments.

<details><summary>Repaired agent answer</summary>

Here is the corpus-level answer, straight from `challenge_corpus` (vocabulary comparison over all matched Britannica–Wikipedia pairs).

**Coverage caveat:** the comparison covers 53 Britannica documents and 51 Wikipedia documents, and counts cover only entries with an accepted match. Matches are reported as provisional lexical matches (not individually verified for subject identity). The Britannica text is OCR, so token counts (e.g. "edwards", "ethiopian/ethiopians") may be affected by OCR noise and case handling; I can't confirm the tool's normalization. Per-entry IDs and scan page IDs aren't available from the aggregate corpus tool — those would require per-entry lookups.

**Words most distinctive of the Britannica vocabulary (vs. Wikipedia), ranked by z-score:**

| term | z-score | Britannica count | Wikipedia count |
|------|---------|------------------|-----------------|
| inches | 3.837 | 16 | 1 |
| native | 3.789 | 26 | 16 |
| british | 3.593 | 39 | 49 |
| edwards | 3.588 | 15 | 2 |
| ethiopians | 3.573 | 14 | 1 |
| placed | 3.522 | 22 | 13 |
| eyes | 3.485 | 18 | 7 |
| island | 3.290 | 19 | 11 |
| marked | 3.188 | 13 | 3 |
| cells | 3.158 | 12 | 2 |
| ethiopian | 3.127 | 10 | 0 |
| abdomen | 2.978 | 10 | 1 |

**Inference:** The strongest Britannica-distinguishing signal is measurement/physical-description vocabulary — "inches" (16 vs 1), "eyes" (18 vs 7), "abdomen" (10 vs 1), "cells" (12 vs 2) — along with the proper nouns "edwards" (15 vs 2) and "ethiopian(s)" (14 vs 1, 10 vs 0). "Native" and "british" appear in both corpora but are far more frequent in Britannica. For reference, the reverse (Wikipedia-distinctive) side is headed by "erigeron" (0 vs 173), "edward" (0 vs 166), "fleabane" (0 vs 154), "esarhaddon" (1 vs 168), and "energy" (0 vs 142).

**Verification:** Real tool output from `challenge_corpus` (status: ok; frequency cosine 0.5049, indicating moderate overall vocabulary overlap). No further work needed unless you want per-entry citations for specific terms.

</details>
