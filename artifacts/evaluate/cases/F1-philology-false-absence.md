# Case study

Case ID: F1-philology-false-absence
Classification: failure
Run record: `artifacts/agent/runs/2026-10-18T114003Z/q05-philology.jsonl` (run `2026-10-18T114003Z`, question `q05-philology`, Hermes session `20261018_134130_6645df`)
Code revision: `6a8987c49d078fc8c2d7c60c008498011e2f6ed0 + uncommitted changes`

## Question

Compare the Britannica article on PHILOLOGY with its Wikipedia article.

## Evidence

- Model: `nvidia/Nemotron-3.5-Super-VL` (expected `nvidia/Nemotron-3.5-Super-VL`: True)
- Tool calls, in order: tool_search, tool_describe, challenge_search, challenge_search, challenge_corpus, challenge_read, challenge_read, challenge_compare
- Britannica entry IDs cited: E0204, E0206
- Wikipedia revision IDs cited: none
- Cited IDs absent from tool results: none
- Quoted passages checked against the tool results of this run:
- exact: "...returned is soon as probable to Philology—— as the year..."
- unsupported: "the philology (did-dialyksia menus..."
- exact: "No accepted Wikipedia match exists for this entry, so no comparison evidence exists."

## Result

The agent stated that the corpus has no Britannica article on PHILOLOGY. Entry E0019 is that article: its OCR headword and running header read PHILLOOGY (scan row 403). challenge_search uses exact word overlap, so it did not find the OCR form, and the agent did not try other spellings. The automatic check passed this run because the answer said that evidence was missing.

Limits: The match stage also rejected E0019, so a comparison would still be missing. The failure is the claim that the entry does not exist.
Repair: Add fuzzy headword search to challenge_search, and an OCR-tolerant title query to the match stage. Record the repaired run separately.

Automatic check: pass. The automatic check uses text rules. This classification comes from a manual review of the answer and the sources.

<details><summary>Agent answer</summary>

## Result: evidence is missing — cannot complete the comparison

The challenge corpus contains **no Britannica article on PHILOLOGY with an accepted Wikipedia match**, so there is nothing to compare.

### What the tools returned

`challenge_search` for `"PHILOLOGY"` and `"philology"` returns exactly two entries, both unrelated to philology:

- **E0204** (scan page `britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:2296`) — an Arctic-exploration narrative about shipwrecks near Greenland and the North Pole. It contains the word "Philology" only once, as stray OCR text inside the narrative ("...returned is soon as probable to Philology—— as the year..."). Match: **rejected** (provisional_lexical; candidate title "Harry Whitney", page_id `7568472`, title_similarity 0.0). `has_comparison: false`.
- **E0206** (scan page `britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:2402`) — an anatomy article about vertebrae/sacral and coccygeal bones. Its only "philology" token is an OCR-garbled fragment: "the philology (did-dialyksia menus..." — clearly a mangled Latin species name, not philology. Match: **rejected**. `has_comparison: false`.

`challenge_compare` on E0204 reports **`no_comparison`**: "No accepted Wikipedia match exists for this entry, so no comparison evidence exists." E0206 would return the same.

### Interpretation (labelled as inference)
The search hits are false positives from noisy OCR: the word "philology" occurs inside unrelated articles, not as a headword. Neither E0204 nor E0206 is a philology article, so neither can serve as the Britannica side of the comparison, and neither has a matched Wikipedia article.

### Conclusion
There is no Britannica PHILOLOGY entry / Wikipedia article pair in this corpus. I cannot compare them, and I will not fill the gap from memory or general knowledge. If you have a specific Britannica entry ID or scan page for a philology article, I can look it up directly.

</details>

## Repaired run

The classification above describes the failed run. This section records a later run after a repair.

Run record: `artifacts/agent/runs/2026-10-18T115609Z/q05-philology.jsonl` (run `2026-10-18T115609Z`, question `q05-philology`, Hermes session `20261018_135725_93a36f`)
Repair outcome: partly fixed

- Tool calls, in order: tool_search, tool_describe, challenge_search, challenge_read, challenge_read, challenge_compare, challenge_read
- Britannica entry IDs cited: E0019
- Wikipedia revision IDs cited: 1349939971
- Cited IDs absent from tool results: none
- Automatic check: pass
- Quoted passages checked against the tool results of this run:
- exact: "The phrase does not occur in this source text."
- exact: "Cushim was the same. We may therefore rest assured, that whatever changes the Ethiopian dialect may have un-dergone in the course of three thousand years, it wa"
- exact: "The writer letters of the Ethiopians, according to Dio-dorus Sicula, were the same with the sacred characters of the Egyptians."
- exact: "Philology (from Ancient Greek φιλολογία (philología) ' love of word ') is the study of language in oral and written historical sources. It is the intersection o"
- exact: "A person who pursues this kind of study is known as a philologist. In older usage, especially British, philology is more general, covering comparative and histo"

Repair: fuzzy headword search in challenge_search and the OCR headword variant in the match stage (PHILLOOGY -> philology). The agent now finds E0019 through a fuzzy headword hit, and the match stage accepts Wikipedia "Philology" (page 23193, revision 1349939971). The false absence is fixed. A new error remains: the agent concludes that E0019 is "not about philology" because the word does not occur in the body, and that no Britannica philology text exists. PHILLOOGY is the running header of scan row 403, and the body discusses Ethiopian letters, dialects, and their relation to Chaldaic and Egyptian. Inference: this is a section of the PHILOLOGY article, so the agent's conclusion is wrong.

<details><summary>Repaired agent answer</summary>

Here is the comparison, built strictly from the challenge tools.

## What the matcher found

`challenge_search("philology")` returned one accepted candidate:

- **Britannica entry E0019**, headword OCR'd as `PHILLOOGY` (fuzzy headword hit: `philloogy`), scan page `britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:403` (scan file `page-0403-44f912e1c323.jpg`), text sha256 `a9b8da2ac1b4afba64894059e7728905c832d0f8c94caf0682386589f50d4e62`.
- **Wikipedia match: "Philology"**, page_id `23193`, status `accepted`, title_similarity `1.0`, method `provisional_lexical`.

This is a **headword/lexical match only** — the matcher fused the OCR headword `PHILLOOGY` to the Wikipedia article "Philology." It is not a content verification.

## What the Britannica text actually says

`challenge_read(E0019, source=britannica, find="philology")` → **`not_found` — "The phrase does not occur in this source text."** The word "philology" appears **zero times** in this Britannica entry.

The entry's body is about Ethiopian/Cushite language origins, not philology as a discipline. Quotes from E0019 (scan page `...:train:403`):

- "Cushim was the same. We may therefore rest assured, that whatever changes the Ethiopian dialect may have un-dergone in the course of three thousand years, it was originally either Chahidae, or at least a branch of that language."
- "The writer letters of the Ethiopians, according to Dio-dorus Sicula, were the same with the sacred characters of the Egyptians."

Distinctive Britannica terms (from the comparison): `ethiopians` (12×), `letters` (12×), `sacred` (8×), `dialect` (4×), `chaldaic` (3×), `egyptians` (5×), `alphabet` (3×) — all 0× in Wikipedia.

## What the Wikipedia article says

**Wikipedia "Philology"**, page_id `23193`, revision_id `1349939971` (revision_url `https://en.wikipedia.org/w/index.php?oldid=1349939971`, CC BY-SA 4.0, text sha256 `44d2da7537cfa1fe1e0525b702337ec51b476f18cfb29fc0878cbeb2657b7218`):

- "Philology (from Ancient Greek φιλολογία (philología) ' love of word ') is the study of language in oral and written historical sources. It is the intersection of textual criticism, literary criticism, history, and linguistics with strong ties to etymology."
- "A person who pursues this kind of study is known as a philologist. In older usage, especially British, philology is more general, covering comparative and historical linguistics."
- "philology" occurs **27×**; `languages` 16×; `linguistics` 8×; `philologist` 6×.

## Comparison metrics (`challenge_compare`, E0019)

- top_terms_jaccard: **0.0471**; frequency_cosine: **0.1549**; length_ratio (wiki/britannica): **2.021** — very low topical overlap.
- `philology`: Britannica **0×**, Wikipedia **27×**.
- Britannica: 593 raw tokens, 480 kept, 342 types, **unverified_rate 0.1906** (19% of tokens unverified — very noisy OCR). Unverified examples: `ethiopie`, `chaldeau`, `cushim`, `chahidae`, `sadger`, `dergone`.
- Wikipedia: 970 tokens, 588 types.

## Conclusion

**The match is wrong for a subject comparison.** The matched Wikipedia article ("Philology," page_id 23193, revision 1349939971) describes philology as a discipline; the only Britannica candidate matched to it (E0019) is not about philology — its text contains no occurrence of "philology" and concerns Ethiopian/Cushite language origins and alleged ties to Chaldean, Hebrew, Sanskrit, and Egyptian. The OCR is noisy (the headword itself reads `PHILLOOGY`, and 19% of tokens are unverified).

**Inference (my interpretation, not a tool finding):** E0019 appears to be a mis-scanned or mislabeled page whose OCR headword was misread as `PHILLOOGY` while the body is an Ethiopian-languages article. Because of this, **no genuine Britannica PHILOLOGY article text is available in this dataset**, so a real philology-vs-philology comparison cannot be produced from this evidence. The evidence gap is missing; I am not filling it from memory.

</details>
