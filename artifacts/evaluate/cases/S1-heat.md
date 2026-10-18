# Case study

Case ID: S1-heat
Classification: success
Run record: `artifacts/agent/runs/2026-10-18T114003Z/q01-heat.jsonl` (run `2026-10-18T114003Z`, question `q01-heat`, Hermes session `20261018_134007_2ae955`)
Code revision: `6a8987c49d078fc8c2d7c60c008498011e2f6ed0 + uncommitted changes`

## Question

How does the Britannica entry on HEAT describe heat, compared with the matched Wikipedia article?

## Evidence

- Model: `nvidia/Nemotron-3.5-Super-VL` (expected `nvidia/Nemotron-3.5-Super-VL`: True)
- Tool calls, in order: tool_search, tool_describe, challenge_search, challenge_read, challenge_read
- Britannica entry IDs cited: E0087
- Wikipedia revision IDs cited: 1333417689
- Cited IDs absent from tool results: none
- Quoted passages checked against the tool results of this run:
- exact: "one of the ... qualities of bodies, produced by fire, and opposed to cold."
- exact: "what we call heat is a particular idea or modification of our own mind, and not any thing ... in the body that occasions it."
- exact: "Heat, [says] Mr Locke, is no more in the fire that burns the finger, than pain is in the needle that pricks it."
- close: "heat in the body that gives it, is only motion; and in the mind, only a particular idea."
- exact: "an agitation of the parts of the body"
- exact: "in the hot body nothing but motion."
- exact: "The degree of heat is measured by the expansion of the air, or spirit in the thermometer."
- exact: "In thermodynamics, heat is defined as the form of energy crossing the boundary of a thermodynamic system by virtue of a temperature difference across the bounda"
- exact: "either thermal energy or temperature, or the human perception of these."
- close: "replaced by the 'mechanical' theory of heat"
- exact: "the very essence of heat... is motion and nothing else"
- exact: "an artifact of our minds."

## Result

The agent found entry E0087, read both sources, and compared the Britannica account of heat as an idea in the mind with the Wikipedia account of heat as energy transfer. It cited the scan page ID and Wikipedia revision 1333417689. The quotes it gives occur in the saved source text.

Limits: The match is provisional_lexical, not checked by the Nemotron embedder and reranker. The Britannica text is OCR with errors; the agent marked its own corrections.


Automatic check: pass. The automatic check uses text rules. This classification comes from a manual review of the answer and the sources.

<details><summary>Agent answer</summary>

## Comparison: Britannica "HEAT" (E0087) vs. Wikipedia "Heat"

### Match validity
The matched Wikipedia article is **Heat** (page_id 19593167, revision_id 1333417689), accepted as a match to Britannica entry **E0087** (headword HEAT, scan page ID `britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:1032`). The match is correct — both treat heat as a physical/philosophical concept.

### What the Britannica entry says (noisy OCR)
The Britannica text is OCR-noisy (e.g. "phylology" for philosophy, "forecary" for elementary, "fanitation" for sensation, "frys" for says, "'S Gravefunde" for 's Gravesande), so exact wording is unreliable, but the sense is clear:

- Heat is "one of the ... qualities of bodies, produced by fire, and opposed to cold." (E0087)
- "what we call heat is a particular idea or modification of our own mind, and not any thing ... in the body that occasions it." (E0087)
- "Heat, [says] Mr Locke, is no more in the fire that burns the finger, than pain is in the needle that pricks it." (E0087)
- "heat in the body that gives it, is only motion; and in the mind, only a particular idea." (E0087)
- Per 's Gravesande, heat in a hot body is "an agitation of the parts of the body" — motion that excites the idea of heat in the mind; "in the hot body nothing but motion." (E0087)
- "The degree of heat is measured by the expansion of the air, or spirit in the thermometer." (E0087)

**Britannica's account:** Heat is fundamentally a subjective sensation/idea in the mind produced by fire's action on our sense organs; in the hot body itself it reduces to motion (agitation of parts). It is defined phenomenologically (Lockean), tied to fire, contrasted with cold, and measured by thermometric expansion.

### What the Wikipedia article says
- "In thermodynamics, heat is defined as the form of energy crossing the boundary of a thermodynamic system by virtue of a temperature difference across the boundary. A thermodynamic system does not contain heat." (Heat, rev. 1333417689)
- In common language "heat" or "warmth" refers to "either thermal energy or temperature, or the human perception of these." (Heat, rev. 1333417689)
- SI unit is the joule; symbol Q introduced by Clausius and Rankine c. 1859. (Heat, rev. 1333417689)
- Historically the caloric theory was "replaced by the 'mechanical' theory of heat" around the end of the 18th century; Bacon (1620): "the very essence of heat... is motion and nothing else"; Galileo described heat as "an artifact of our minds." (Heat, rev. 1333417689)

### How they differ (my inference)
The two sources converge on one point: both acknowledge that heat is tied to the motion of particles and that the sensation of heat is mind-dependent (Britannica via Locke/'s Gravesande; Wikipedia via Galileo/Bacon and its "common language" note). But they define heat differently:

1. **Ontology:** Britannica treats heat as a sensation/idea in the mind (with motion in the body); Wikipedia's primary definition treats heat as **energy in transit across a boundary due to temperature difference**, explicitly stating a system "does not contain heat."
2. **Source/cause:** Britannica ties heat to **fire**; Wikipedia ties it to a **temperature difference** (and, secondarily, to internal thermal energy).
3. **Measurement:** Britannica uses expansion of air/spirit in a thermometer; Wikipedia uses the joule (SI), with BTU/calorie and watt for rate.
4. **Framework:** Britannica is a pre-modern, philosophical account; Wikipedia is a modern thermodynamic one, framed by the caloric-to-mechanical-theory transition.

So the Britannica entry describes heat primarily as a mind-dependent sensation of fiery motion, while the matched Wikipedia article defines it objectively as energy transfer driven by temperature difference.

</details>
