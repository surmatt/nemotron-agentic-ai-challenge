# Case study

Case ID: S3-locomotive-missing
Classification: success
Run record: `artifacts/agent/runs/2026-10-18T114003Z/q06-locomotive.jsonl` (run `2026-10-18T114003Z`, question `q06-locomotive`, Hermes session `20261018_134154_59e708`)
Code revision: `6a8987c49d078fc8c2d7c60c008498011e2f6ed0 + uncommitted changes`

## Question

What does Britannica say about the steam locomotive, compared with Wikipedia?

## Evidence

- Model: `nvidia/Nemotron-3.5-Super-VL` (expected `nvidia/Nemotron-3.5-Super-VL`: True)
- Tool calls, in order: tool_search, tool_describe, tool_describe, challenge_search, challenge_search, challenge_search, challenge_search, challenge_corpus, challenge_search, challenge_search
- Britannica entry IDs cited: E0040
- Wikipedia revision IDs cited: none
- Cited IDs absent from tool results: none
- Quoted passages checked against the tool results of this run:
- exact: "a compound machine, made of one or more mechanical powers, as levers, pullies..."

## Result

No entry about the steam locomotive exists in the sample. The agent searched four queries, reported no_results, and did not fill the gap from memory. It rejected the ENGINE entry as a different subject.

Limits: The sample has 100 scans, so absence in the sample says nothing about the full encyclopaedia.


Automatic check: pass. The automatic check uses text rules. This classification comes from a manual review of the answer and the sources.

<details><summary>Agent answer</summary>

The evidence is missing. The challenge corpus does not contain a Britannica entry on the steam locomotive, so I cannot produce a Britannica-vs-Wikipedia comparison for that subject.

What I checked (all via `challenge_search`, the required first step):

| Search query | Result |
|---|---|
| "steam locomotive" | no_results |
| "locomotive" | no_results |
| "steam" | no_results |
| "railway locomotive" | no_results |

The closest topical hit was "steam engine," which returned only one relevant entry, **E0040 (headword "ENGINE")**, scan page `britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:523`, matched to Wikipedia article "Engine" (page_id 9640, title_similarity 1.0, has_comparison: true). Its opening text is about mechanics generally — "a compound machine, made of one or more mechanical powers, as levers, pullies..." — not about a steam locomotive. So that match describes a different subject; treating it as the steam-locomotive entry would be a wrong match, and I have not done that.

Corpus scope: 57 Britannica entries / 55 Wikipedia articles, all matched by provisional_lexical method. "Steam"/"locomotive" appear as no distinctive corpus terms, confirming the subject is not represented.

Per the rules, when a tool reports no_results/no_match, the evidence is missing and I will not fill the gap from memory or outside knowledge. I also won't state an edition, year, or author, since no tool result provided one. Note that the Britannica text is noisy OCR (e.g., E0040 shows "Sì," "ferws," "fulanany"), which would further limit any OCR-derived claim even if the entry existed.

Bottom line: there is no Britannica steam-locomotive entry in this corpus to compare with Wikipedia's steam-locomotive article. If you have a specific Britannica entry ID (E####) you believe covers it, I can read it and run `challenge_compare` against its Wikipedia match.

</details>
