# Match with LLM titles

The match stage can ask Super 3.5 VL for likely Wikipedia titles of each entry.
This file reports whether the extra searches find better matches.

Code: `src/nemotron_challenge/match.py` (step 6 in the module docstring).
Switch: `CHALLENGE_MATCH_LLM=0` turns the LLM titles off. They are on when `SUPER_API_KEY` is set.

## Method

1. Super VL reads the headword and the first 1,200 characters of the entry text.
   Temperature 0, reasoning off, at most 300 tokens.
2. It returns up to 3 likely English Wikipedia titles and up to 8 modern topic words, as JSON.
3. Each title gets one BM25 search with 100 hits.
   Only hits whose title has similarity 0.9 or more to the LLM title are kept.
4. The kept hits go to the reranker before the other candidates. The cap stays at 32 candidates.
5. The reranker, the thresholds, and the accept rule do not change.
6. The reply is saved unchanged in `match/llm/`, keyed by the entry text checksum.

The topic words are saved but not searched. See variant v1 below.

## Why a title filter

BM25 often ranks the main article low.
The query `erfurt` does not return the article "Erfurt" in its top 20.
"Erfurt" appears only at rank 17 of the headword-and-keywords query.
A search for the LLM title with 100 hits and a title filter finds it.

## Runs

All three variants use the same corrected text (a full run on 2026-10-18, 250 entries) and the same code revision `9f2e6c3` with the match change.
Only the match setting differs.

| Variant | Extra searches |
| --- | --- |
| base | none |
| v1 | each LLM title and the joined topic words as plain BM25 queries (20 hits each) |
| v2 | each LLM title with 100 hits and the title filter (the current code) |

Super VL calls for v1 and v2: 202, no failures.
Mean tokens per call: 349 prompt, 59 completion.
Match stage time: 164 s (base), 225 s (v2).

## Label review

The labels in `match_labels.json` list the correct candidates among the candidates of the saved run.
v1 and v2 can choose articles that the labeller did not see.
The coding agent read the entry text and the article opening for each such pick in v2.
It used the rule of `match_labels.json`. Nobody else reviewed the result.

- Correct (added to the accept list): Mount Etna (E0006), Bryan Edwards (politician) (E0107),
  Prison escape (E0126), Executive (government) (E0153), Ataraxia (E0185), Cabinet (room) (E0226).
- Wrong: Tycho Brahe (E0112, the segment is mostly HUET), Hugh (E0113, also chosen by base).

The review is in `match_label_review_llm.json`. With it, 47 of the 60 labelled entries have a correct article.
Two v1 picks were not reviewed (Litre for E0002, Boraginaceae for E0047). They count as false positives.

## Results

Scores on the 60 labelled entries with the review added:

| Variant | Accepted | Correct | Wrong | Precision | Recall | F1 | F1 on the test half |
| --- | --- | --- | --- | --- | --- | --- | --- |
| base | 28 | 23 | 5 | 0.821 | 0.489 | 0.613 | 0.537 |
| v1 | 29 | 23 | 6 | 0.793 | 0.489 | 0.605 | 0.550 |
| **v2** | **31** | **26** | **5** | **0.839** | **0.553** | **0.667** | **0.636** |

On all 202 searched entries, base accepts 88 and v2 accepts 92.

- v2 finds articles that BM25 did not return: Ataraxia, Mount Etna, Executive (government), Cabinet (room).
- v2 removes one wrong match: DAMSEL is no longer matched to "Damsel, Missouri".
- v2 loses three correct matches: Coin (E0099), Lightning (E0167), Pierre Daniel Huet (E0112).
  The extra candidates are close to the topic, so the reranker margin falls below 0.5.
- v1 adds related pages that push correct candidates out of the 32 that the reranker scores.
  Example: "Erfurt" drops out, and ERFURT is rejected.

## Limits

- The thresholds were calibrated on the base candidates. A new calibration on the v2 candidates can recover the lost matches, but it uses the same 60 labels.
- One labeller (the coding agent) made the labels and the review.
- The test half has 30 entries, so one entry changes F1 by about 0.03.
- Agent runs were not repeated with the v2 matches.
