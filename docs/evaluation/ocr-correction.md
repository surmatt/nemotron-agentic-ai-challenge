# OCR correction with Super VL

Parse 3.5 extracts each scan. Then Super 3.5 VL reads an enlarged crop of each Parse block together with the Parse text and returns corrected text.
This file reports how much the correction improves the text, measured against hand transcriptions.

Code: `src/nemotron_challenge/correct.py` (stage `correct`) and `src/nemotron_challenge/ocr_eval.py` (gold set and metrics).
Saved runs: `artifacts/correct/raw/<variant>/` (one unchanged reply per block), `artifacts/correct/eval.json` (scores).

## Method

1. Cut the Parse box of each running-text block from the scan, with a 6-pixel margin. Enlarge it 3 times.
2. Send the crop and the Parse text to `nvidia/Nemotron-3.5-Super-VL` at temperature 0, with reasoning off.
3. The prompt gives the transcription rules and forbids words that the image does not show.
4. Keep the Parse text when the box is too small to hold a line, or when the call fails.
5. Flag a block for review when Super VL empties it or makes it much longer.

## Gold set

- 30 blocks from 15 scans, chosen with seed 20261018 (`docs/evaluation/ocr_gold.json`).
- 29 blocks have text: 12,845 characters and 2,258 words. One box (G21) holds no text.
- Scan 1032 is excluded because its Super VL output was seen in the first probe.
- The transcriber worked from enlarged crops with the box drawn, without the Parse or Super VL text.
- Scores ignore case and accents. The long s counts as s. Line-break hyphens are joined.

## Results

| System | CER | WER | Words not in gold per 100 | Blocks better than Parse | Blocks worse |
| --- | --- | --- | --- | --- | --- |
| Parse 3.5 | 12.2% | 25.1% | 21.1 | – | – |
| Parse 3.5 + long-s rule | 12.1% | 24.6% | 20.6 | 8 | 1 |
| **Parse + Super VL, block crop, no reasoning** | **1.8%** | **3.0%** | **2.5** | **28** | **1** |
| Parse + Super VL, block crop, reasoning | 2.9% | 3.7% | 2.8 | 25 | 3 |
| Super VL, block crop, no Parse text | 7.0% | 12.1% | 10.8 | 19 | 10 |
| Parse + Super VL, whole page, no reasoning | 24.9% | 35.3% | 23.8 | 16 | 3 |

- The chosen variant lowers CER 6.8 times. Without the disputed block G08, CER falls from 12.1% to 0.8%.
- The Parse text helps: without it, CER is 7.0% instead of 1.8%.
- Reasoning makes it worse and slower: 13.9 s and about 4,200 tokens per block, against 1.1 s and about 100 tokens.
  One reasoning call stopped at the 12,000-token limit.
- The whole page does not work: the model often transcribes the wrong region (G22: CER 208%).
- Empty box G21: Parse gave it 204 characters of text. Every Super VL variant returned no text.

## Errors that remain

- G08 is the only block that got worse. Super VL also transcribed a line that the gold left out as cut by the box edge.
  The text is real. The difference is a box-boundary choice.
- Super VL sometimes replaces a word with a plausible other word: "voluminous" for "posthumous" (G04), "refused" for "resolved" (G03).
- Some long-s errors stay ("flockings" for "stockings", G01).

## Full run

| Decision | Blocks |
| --- | --- |
| Super VL text | 1,105 |
| Super VL text, flagged: much longer than Parse | 40 |
| Super VL text, flagged: emptied | 2 |
| Parse text: box too small | 29 |
| Parse text: Super VL call failed | 1 |
| Parse text: tables, pictures, or non-text pages | 39 |

- The share of dictionary words in the corrected blocks rose from 78.2% to 83.6% (inference: a proxy, not accuracy).
- Headword entries rose from 159 to 174. For example, "WILLIN" became "WILLIAM" and "ENDYMON" became "ENDYMION".
- The flag "much longer" often marks lines that Parse lost (scan 1649, block 5: Parse kept about 2 of 23 lines).
  In that block Super VL also joined the Parse text to the start of the region with invented words ("clasped arms").
- Super VL also removed text that Parse invented (scan 546, block 0: a modern sentence about "users").

## Effect on the later stages

Both runs use the same match and compare code. Only the entry text differs.
The Parse-text run is kept in `artifacts/match-parse-text-2026-10-18/` and `artifacts/compare-parse-text-2026-10-18/`.

| Measure | Parse text | Corrected text |
| --- | --- | --- |
| Entries | 241 | 249 |
| Entries searched | 188 | 201 |
| Accepted matches (provisional lexical rule) | 53 | 80 |
| Britannica tokens outside the vocabulary | 18.8% | 10.6% |
| Mean frequency cosine of matched pairs | 0.144 | 0.190 |

- New correct matches include CONCHOLOGY, STEAM-ENGINE, THRACE, OPTICS, THORAX, and ERFURT.
- The corrected headword makes the lexical rule accept more pairs, so it also accepts more wrong pairs:
  AMICTUS → "Ambitus", PHARMACY → "Pharmacis", HELVOETSLUYS → a painting. The reranker must check these.
- Example of better evidence for the agent: entry NAXOS now reads "capital of the Isle of Naxos" instead of "capital of the lake of Naoxe".

## Limits

- One transcriber made the gold set, and nobody reviewed it. Small print at 600 pixels makes some letters uncertain.
- 29 scored blocks are a small sample. Tables, formulas, pictures, and headers were not scored.
- Running headers are not corrected, so the header "PHILLOOGY" stays.
