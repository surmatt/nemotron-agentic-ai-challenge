# Case study

Case ID: F3-heat-no-rules-edition
Classification: failure
Run record: `artifacts/agent/runs/2026-10-18T113829Z-trial/q01-heat-nopolicy.jsonl` (run `2026-10-18T113829Z-trial`, question `q01-heat-nopolicy`, Hermes session `20261018_133829_0fb82c`)
Code revision: `6a8987c49d078fc8c2d7c60c008498011e2f6ed0 + uncommitted changes`

## Question

How does the Britannica entry on HEAT compare with Wikipedia? Use the tools and cite IDs.

## Evidence

- Model: `nvidia/Nemotron-3.5-Super-VL` (expected `nvidia/Nemotron-3.5-Super-VL`: True)
- Tool calls, in order: tool_search, tool_search, tool_describe, challenge_search, challenge_read, challenge_read, challenge_compare
- Britannica entry IDs cited: E0087
- Wikipedia revision IDs cited: 1333417689
- Cited IDs absent from tool results: none
- Quoted passages checked against the tool results of this run:
- exact: "a particular idea or modification of our own mind,"
- exact: "Heat... is no more in the fire that burns the finger, than pain is in the needle that pricks it"

## Result

In the first trial, the prompt had no evidence rules. The agent called the source the "1911 Encyclopaedia Britannica". No tool result gives an edition or year, and the long s in the scans indicates an earlier printing (inference). The automatic check passed because it does not test unsupported metadata.

Limits: This trial used the same tools and artifacts but a different prompt. The repaired prompt (rule: do not state an edition or year without tool evidence) produced run 2026-10-18T114003Z q01-heat, which states no edition.
Repair: Evidence rule added to integrations/hermes/questions.json. See case S1-heat for the repaired run.

Automatic check: pass. The automatic check uses text rules. This classification comes from a manual review of the answer and the sources.

<details><summary>Agent answer</summary>

Comparison complete. Sources and citations:

MATCHED PAIR
- Britannica entry E0087, headword "HEAT" (1911 Encyclopaedia Britannica, OCR). Scan page britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:1032 (file page-1032-e28420685b47.jpg), text_sha256 59eca6ed30a9a491053501c57f5c1d69d2ae6e971b1bc9c60ff5f05081742ded. 1,926 chars, 166 raw tokens, 95 types.
- Wikipedia article "Heat", page_id 19593167, revision_id 1333417689 (https://en.wikipedia.org/w/index.php?oldid=1333417689), CC BY-SA 4.0, text_sha256 75f20ec52047d514717e7f0a3736c7ac2f984a7a233c03ec98d40c6a00b498c6. 60,960 chars, 4,839 tokens, 1,428 types.
- Match: accepted, method provisional_lexical, title_similarity 1.0. A saved comparison exists for this entry (challenge_compare on E0087).

WHAT EACH SAYS
- Britannica (E0087): a philosophical, sensation-based account. Heat is "a particular idea or modification of our own mind," not anything existing in the body; in the body it is only motion. It quotes Locke ("Heat... is no more in the fire that burns the finger, than pain is in the needle that pricks it") and 's Gravesande (heat as agitation of the body's parts). Heat is produced by fire, opposed to cold, the sun is the principal source, and degree of heat is measured by thermometer expansion. OCR is noisy (10.24% unverified tokens; e.g. "phylology" = philosophy, "fanitation" = sensation).
- Wikipedia (Heat, page_id 19593167): modern thermodynamics. Heat is energy crossing a thermodynamic system's boundary because of a temperature difference; a system does not contain heat. SI unit is the joule, rate in watts, symbol Q introduced by Clausius and Rankine c. 1859, sign convention Q<0 released / Q>0 absorbed, plus heat flux and calorimetry. It covers the history (caloric theory, phlogiston, Bacon/Galileo/Hooke/Boyle on heat as particle motion, Galileo's heat as "artifact of our minds") — the old mind-based idea survives only as historical context.

COMPARISON METRICS (challenge_compare, E0087; word frequencies, log-odds z-scores with informative Dirichlet prior)
- Jaccard (top terms): 0.0484
- Frequency cosine: 0.4838
- Length ratio (Wikipedia / Britannica): 32.48 — Wikipedia is roughly 32 times longer.
- Shared term counts (Britannica / Wikipedia): heat 12/258, body 7/60, fire 7/3, hot 5/25, idea 5/4, motion 4/16, cold 2/21, produced 3/2, effect 3/2, bodies 2/17.

DISTINCTIVE TERMS
- Britannica: feeling (z 0.805), atmosphere (0.805), fire (0.792), mind (0.751), hence (0.684) — the sensation/ideas-in-mind frame.
- Wikipedia: heat (z 7.075), temperature 4.675 (89 vs 0), energy 4.553 (106 vs 0), transfer 3.667 (56 vs 0), work 3.414 (82 vs 0), system 3.286 (65 vs 0), quantity 3.25 (48 vs 0) — thermodynamics, units, energy transfer.

BOTTOM LINE: Both agree heat is not a substance residing in a body and link heat to motion (Britannica: motion of body parts; Wikipedia: particle motion / mechanical theory of heat). They split on framework: Britannica treats heat as a sensation/idea in the mind produced by fire; Wikipedia treats it as measurable energy transfer (joules) across thermodynamic boundaries. Vocabulary overlap is low (Jaccard 0.0484) and Wikipedia is ~32x the length.

</details>

## Repaired run

The classification above describes the failed run. This section records a later run after a repair.

Run record: `artifacts/agent/runs/2026-10-18T115609Z/q01-heat.jsonl` (run `2026-10-18T115609Z`, question `q01-heat`, Hermes session `20261018_135610_e76c99`)
Repair outcome: fixed

- Tool calls, in order: tool_search, tool_describe, challenge_search, challenge_read, challenge_read, challenge_compare
- Britannica entry IDs cited: E0087
- Wikipedia revision IDs cited: 1333417689
- Cited IDs absent from tool results: none
- Automatic check: pass
- Quoted passages checked against the tool results of this run:
- exact: "one of the forecary qualities of bodies, produced by fire, and opposed to cold"
- close: "what we call heat is a particular idea or modification of our own mind, and not any thing existing in the body that occasions it"
- exact: "Heat, [says] Mr Locke, is no more in the fire that burns the finger, than pain is in the needle that pricks it."
- unsupported: "heat in the body ... is only motion; and in the mind, only a particular idea"
- exact: "an agitation of the parts of the body, made by means of the fire contained in it ... in the hot body nothing but motion."
- exact: "The degree of heat is measured by the expansion of the air, or spirit in the thermometer."
- exact: "In thermodynamics, heat is defined as the form of energy crossing the boundary of a thermodynamic system by virtue of a temperature difference across the bounda"
- exact: "English 'heat' or 'warmth' ... refers to either thermal energy or temperature, or the human perception of these."
- exact: "the very essence of heat ... is motion and nothing else"
- exact: "a particular idea ... of our own mind"

Repair: the evidence rule against an unsupported edition, year, or author. Run 2026-10-18T114003Z q01-heat (case S1) and this later run state no edition or year.

<details><summary>Repaired agent answer</summary>

Here is the comparison, based only on the challenge tools.

## Match check

`challenge_search` for "HEAT" returns entry **E0087** (headword HEAT) with an **accepted** match to Wikipedia **"Heat"**, page_id **19593167**, title_similarity 1.0 (challenge_search; confirmed by challenge_compare). The matched article covers the same subject (heat), so the match is valid. `challenge_compare` reports the comparison exists (`has_comparison: true`): Jaccard 0.0481, frequency cosine 0.4832, Wikipedia ~32× longer than Britannica (length ratio 32.26).

## How each source describes heat

**Britannica, entry E0087 (scan page `britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:1032`):**

- Opens by defining heat as "one of the forecary qualities of bodies, produced by fire, and opposed to cold" — a quality of bodies, tied to fire and cold.
- Treats heat as sensation/idea: "what we call heat is a particular idea or modification of our own mind, and not any thing existing in the body that occasions it"; "Heat, [says] Mr Locke, is no more in the fire that burns the finger, than pain is in the needle that pricks it."
- Reduces heat to motion: "heat in the body ... is only motion; and in the mind, only a particular idea"; per "'S Gravefunde" ('s Gravesande), heat is "an agitation of the parts of the body, made by means of the fire contained in it ... in the hot body nothing but motion."
- Measurement: "The degree of heat is measured by the expansion of the air, or spirit in the thermometer."

**Wikipedia, "Heat" (page_id 19593167, revision_id 1333417689):**

- Defines heat strictly: "In thermodynamics, heat is defined as the form of energy crossing the boundary of a thermodynamic system by virtue of a temperature difference across the boundary. A thermodynamic system does not contain heat."
- Quantifies it: SI unit is the joule; sign convention Q < 0 (released) / Q > 0 (absorbed); heat-transfer rate is Q-dot.
- Separately notes common usage: "English 'heat' or 'warmth' ... refers to either thermal energy or temperature, or the human perception of these."
- History section: caloric theory replaced by the "mechanical" theory of heat; Bacon (1620) — "the very essence of heat ... is motion and nothing else"; Galileo — heat as "an artifact of our minds"; Hooke and Boyle — heat as motion of particles.

## Comparison (my interpretation)

Both sources link heat to the motion of particles/bodies and both acknowledge a perceptual side (Britannica: heat is "a particular idea ... of our own mind"; Wikipedia: common usage includes "the human perception" of thermal energy, and Galileo called heat an artifact of the mind). That shared ground is an inference from the texts, not a stated equivalence.

The core difference is definitional: Britannica presents heat as a felt quality/idea of bodies produced by fire, judged against cold and read off a thermometer — a pre-thermodynamic, sensation-based account. Wikipedia presents heat as energy in transfer across a system boundary due to a temperature difference, explicitly stating a system does not *contain* heat, measured in joules with a formal sign convention. These are different definitions, not restatements of one another.

## OCR caveat

The Britannica text is noisy OCR: challenge_compare flags 16 unverified tokens (9.64% unverified rate), e.g. "forecary," "fanitation," "exfiling," "frys," "fuch." Exact wording of Britannica's claims is therefore uncertain; the scan page ID above is the authority for verification. No edition, year, or author is stated by any tool result, so I give none.

</details>
