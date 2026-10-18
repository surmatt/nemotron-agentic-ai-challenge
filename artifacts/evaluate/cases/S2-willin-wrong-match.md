# Case study

Case ID: S2-willin-wrong-match
Classification: success
Run record: `artifacts/agent/runs/2026-10-18T114003Z/q07-willin.jsonl` (run `2026-10-18T114003Z`, question `q07-willin`, Hermes session `20261018_134213_5e581a`)
Code revision: `6a8987c49d078fc8c2d7c60c008498011e2f6ed0 + uncommitted changes`

## Question

Compare the Britannica entry WILLIN with its matched Wikipedia article. Is the match correct?

## Evidence

- Model: `nvidia/Nemotron-3.5-Super-VL` (expected `nvidia/Nemotron-3.5-Super-VL`: True)
- Tool calls, in order: tool_search, tool_describe, challenge_search, challenge_read, challenge_read, challenge_compare
- Britannica entry IDs cited: E0012
- Wikipedia revision IDs cited: 1201363924
- Cited IDs absent from tool results: none
- Quoted passages checked against the tool results of this run:
- exact: "WILLIN, the name of federal kings of England. See ENOLAND, n 87--01, and BITAIN, n' 302."
- exact: "a factory of Afin [Afin?] belonging to the East India company, feated on one of the branches of the river Ganges, in the kingdom of Bengal,"
- close: "Willin' may refer to: Willin' (album), a 1999 album by Jon Randall; 'Willin'' (song), a song by Little Feat, written by lead singer Lowell George in 1970."

## Result

The matcher paired entry E0012 (OCR headword WILLIN) with the Wikipedia page "Willin'", which lists an album and a song. The agent read both texts, cited the comparison metrics, and stated that the match is wrong. The Britannica text mentions the East India Company, Bengal, and the Ganges, which the agent quoted.

Limits: The agent's identification of the place as Fort William in Calcutta is an inference from garbled OCR. It labelled it as an inference.


Automatic check: pass. The automatic check uses text rules. This classification comes from a manual review of the answer and the sources.

<details><summary>Agent answer</summary>

## Answer

**No, the match is not correct.**

### Evidence

**Britannica entry WILLIN (E0012)** — scan page `britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:258`:

The OCR text reads: "WILLIN, the name of federal kings of England. See ENOLAND, n 87--01, and BITAIN, n' 302." It then describes "_For-WILLIAMS_" (likely Fort William), "WILLAN's Port," "a factory of Afin [Afin?] belonging to the East India company, feated on one of the branches of the river Ganges, in the kingdom of Bengal," a town called "_California_" (likely Calcutta), and the "_Blak Hels_" (Black Hole), with events in 1757 involving the "nahoof Bengal" (nawab of Bengal). The text is heavily OCR-corrupted, but the distinctive terms — factory, Bengal, East India Company, Ganges, Black Hole, 1757, nawab — point to Fort William in Calcutta, a British East India Company fort. [Britannica E0012, scan page 258]

**Matched Wikipedia article "Willin'"** (page_id 43635161, revision_id 1201363924):

The article is a disambiguation page: "Willin' may refer to: Willin' (album), a 1999 album by Jon Randall; 'Willin'' (song), a song by Little Feat, written by lead singer Lowell George in 1970." [Wikipedia page 43635161, revision 1201363924]

### Why the match is wrong

1. **Different subjects entirely.** The Britannica entry is about a historical fort in Bengal, India (Fort William / East India Company / Black Hole of Calcutta). The Wikipedia article is a music disambiguation page about an album and a song. They do not describe the same subject.

2. **Near-zero lexical overlap.** The saved comparison reports a Jaccard of 0.0089 and a frequency cosine of 0.0479 — essentially no shared vocabulary beyond the headword "willin" itself. The only shared term is "willin" (1 occurrence in Britannica, 3 in Wikipedia). [challenge_compare, E0012]

3. **Match method was purely lexical.** The match was accepted via "provisional_lexical" with title_similarity 1.0, meaning it matched on the headword string alone ("WILLIN" → "Willin'") without verifying subject similarity. That is a false positive.

### Inference

The Britannica entry WILLIN (E0012) concerns Fort William in Bengal, and its correct Wikipedia match would be an article about Fort William, Calcutta (or the Black Hole of Calcutta), not the music disambiguation page "Willin'." The accepted match is incorrect.

</details>

## Repaired run

The classification above describes the failed run. This section records a later run after a repair.

Run record: `artifacts/agent/runs/2026-10-18T115609Z/q07-willin.jsonl` (run `2026-10-18T115609Z`, question `q07-willin`, Hermes session `20261018_135817_d04181`)
Repair outcome: match repaired

- Tool calls, in order: tool_search, tool_describe, challenge_search, challenge_read, challenge_read
- Britannica entry IDs cited: E0012
- Wikipedia revision IDs cited: none
- Cited IDs absent from tool results: none
- Automatic check: pass
- Quoted passages checked against the tool results of this run:
- exact: "WILLIN, the name of federal kings of England. See ENOLAND, n 87--01, and BITAIN, n' 302."
- exact: "_WILLAN's Port,_ is a factory of Afin belonging to the East India company, feated on one of the branches of the river Ganges, in the kingdom of Bengal,"
- close: "In 1757 it was fur-pulled by the nahoof Bengal, who took its, and put met of those that had made resilience into place called the _Blak Hels_..."
- exact: "no candidate with title similarity >= 0.85 outside media titles"
- exact: "This entry has no accepted Wikipedia article."

After the list-page repair, the match stage rejects "Willin'" because its text opens with "may refer to". The best remaining candidate ("Willin Low", title similarity 0.75) is rejected. The agent reports the rejected match, finds no comparison, and still states that the old pairing would be wrong. The success classification describes the earlier run.

<details><summary>Repaired agent answer</summary>

## Result: The match is NOT correct

### Evidence from the tools

**Britannica entry (E0012, headword WILLIN)**
- Scan page ID: `britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:258` (scan file `page-0258-631a7ae7df34.jpg`)
- The entry opens: *"WILLIN, the name of federal kings of England. See ENOLAND, n 87--01, and BITAIN, n' 302."*
- It continues with what reads (despite heavy OCR noise) like an account of an East India Company factory in Bengal: *"_WILLAN's Port,_ is a factory of Afin belonging to the East India company, feated on one of the branches of the river Ganges, in the kingdom of Bengal,"* and *"In 1757 it was fur-pulled by the nahoof Bengal, who took its, and put met of those that had made resilience into place called the _Blak Hels_..."* ("Blak Hels" = Black Hole; "nahoof Bengal" = nawab of Bengal).
- The text is noisy OCR (e.g., "BITAIN" for Britannia, "fur-pulled", "feated", "nahoof"), so my reading that this concerns **Fort William in Bengal/Calcutta** is an **inference**, not a verbatim fact.

**Matched Wikipedia article (proposed, rejected)**
- `challenge_search` returned a *provisional* match: title **"Willin Low"**, Wikipedia page_id **33853596**, title_similarity **0.75**.
- Match status: **rejected** (method `provisional_lexical`), reason: *"no candidate with title similarity >= 0.85 outside media titles"* — below the 0.85 acceptance threshold.
- `has_comparison`: false (no saved word-frequency comparison exists).
- `challenge_read(source=wikipedia)` for E0012: **no_match** — *"This entry has no accepted Wikipedia article."*

### Conclusion

The match is incorrect. The system's own matcher rejected the pairing (0.75 similarity < 0.85 threshold, and no accepted Wikipedia article exists for this entry). The proposed article "Willin Low" (page_id 33853596) is a personal name and does not describe the same subject as the Britannica entry, which (per the OCR-noisy text) concerns English kings and an East India Company fort/factory in Bengal. There is no valid Wikipedia match to compare against here — the evidence for a correct match is missing.

</details>
