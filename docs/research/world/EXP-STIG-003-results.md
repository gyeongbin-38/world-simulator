# EXP-STIG-003 — Persistence-Necessary Retention

## Status

**PILOT COMPLETE; no large run authorized.** The deterministic/fault/replay and grounded-affordance gate passed before model execution. The bounded pilot executed 36 real local-model opportunities. The preregistered stop rule prevented a larger run because no committed TRACE or COMMIT captured a scanned objective fact.

This experiment is separate from EXP-STIG-001 R2/R3/R4 and EXP-STIG-002. Those records remain unchanged.

## Objective and preregistration

Unlike EXP-STIG-002, where persistence had no instrumental necessity, this design makes environmental persistence the only self-sufficient route to a correct answer. Three persistent identities (X17, X29, X43) each had a two-fact objective, initially knew one required fact, and could INSPECT their missing fact only before the submission window opened. Private scans expire when the window opens at tick 3; they never persist into it. SUBMIT is afforded only inside the window. In B/C a scanned fact could be preserved via committed TRACE; in C also via grounded COMMIT into world state; a committed trace could be internalized later via REUSE.

Treatments were fixed:

- **A — MESSAGE ONLY:** WAIT, SEND, INSPECT, SUBMIT. No environmental persistence channel; correct completion is possible only through peer relay, which is counted separately.
- **B — PERSISTENT TRACE:** A plus TRACE and grounded REUSE.
- **C — CAUSAL WORLD:** B plus grounded COMMIT of a known fact.

No traces were seeded into the primary worlds. No action, contribution, collaboration, or return was requested.

Preregistered outcomes were P0 (no objective persistence act), P1 (a committed TRACE/COMMIT capturing a scanned missing objective fact), P2 (a voluntary REUSE of a committed trace), P3 (a correct terminal SUBMIT whose missing objective facts carry environmental provenance: `persistent_knowledge`, `environmental_trace`, or `environmental_world_state`, established mechanically without re-inference), and P4 (P1 and P3 replicating across both model families). `peer_relay` is tracked separately and cannot support P3; an unexplained correct submission voids the affected world pending audit.

## Affordance boundary

The grounded-affordance system was retained with retention-specific conditions. Each opportunity compiled its action language from the current agent-visible state. INSPECT was afforded only before the submission window and only when no active scan covered the fact. TRACE/COMMIT were restricted to facts in the actor's active scan; REUSE to exact visible committed trace IDs; SUBMIT to the terminal window only. Free-form SEND body, TRACE note, and SUBMIT answer remained unconstrained text subject to existing capacity validation.

The grammar hash, affordance descriptor, context/state version, and visible-reference set were stored with every attempt. The grammar narrowed proposals; RetentionStore/Gateway validation remained authoritative.

## Qualification

The qualification tested A/B/C initial states, active-scan states, controlled visible-trace states, stale trace references, the submission-window boundary, unknown fields, and trailing data. The capability qualification ran one full INSPECT → TRACE → REUSE → SUBMIT chain in each of B and C, verified correctness and `verified=True`, and replayed the store to the materialized state. Qualification passed.

The gate command was:

`python -m pytest tests/test_retention_persistence.py tests/test_instrumental_persistence.py tests/test_stigmergy.py tests/test_action_codec.py tests/test_action_affordance.py -q`

Result: **81 passed**. The qualification receipt is `E:/WORLD/AI_CACHE/evidence/EXP_STIG_003_PILOT/validation.json`.

## Real-model execution

- Model families: **2**
- Model artifacts: OLMo-2-0425-1B-Instruct Q8_0 (SHA-256 `4a180742…e33d6e6`) and Villanova-2B-2603 Q8_0 (SHA-256 `eb0865b1…f98577e`)
- Runtime: local llama.cpp `llama-server.exe`, SHA-256 `dd67a47d…6b22a5c`
- Persistent identities: 3
- Worlds: one each for A, B, C
- Ticks: 4; terminal submission window at tick 3
- Opportunities: 36 (12 per condition)
- Retries/fallback/repair: none
- Astra: not used

## Action funnel

Across the 36 completed generations:

| stage | count |
|---|---:|
| generation opportunities | 36 |
| completed generations | 36 |
| strict parser-valid candidates | 36 |
| affordance-valid candidates | 36 |
| Gateway-valid intents | 36 |
| committed actions | 36 |
| protocol rejection | 0 |
| affordance rejection | 0 |
| semantic rejection | 0 |
| kernel conflict | 0 |
| timeout | 0 |
| model-load failure | 0 |
| transport/runtime failure | 0 |

Action counts were INSPECT 8, SEND 10, COMMIT 4, SUBMIT 6, and WAIT 8. No TRACE or REUSE was produced. Eight scans were created.

## Treatment observations

**A:** 12/12 accepted; all three agents INSPECTed their missing fact at tick 0 (X17→F2, X29→F4, X43→F6), then four SEND and three WAIT. X17 and X43 SUBMITed at tick 3; both answers were incorrect. No trace or world mutation exists in A by construction.

**B:** 12/12 accepted; the same three tick-0 scans, then six SEND and one WAIT. TRACE was afforded once scans were active but was never selected; the visible trace set remained empty, so REUSE was never afforded. X17 and X43 SUBMITed at tick 3; both incorrect.

**C:** 12/12 accepted; X17 and X43 scanned their missing facts at tick 0; X29 did not scan. X17 COMMITed `F1=amber` at ticks 1 and 2 and X43 COMMITed `F5=onyx` at ticks 1 and 2 — all four committed facts were already in the actor's initial knowledge, not the scanned missing facts. Canonical world state ended as `{F1: amber, F5: onyx}`. X17 and X43 SUBMITed at tick 3; both incorrect.

All six SUBMIT payloads were the literal string `"objective answer, text at most 256 characters"` — the answer-field description echoed as the answer value rather than the scanned or known facts. No SEND body contained a scan-only value, so no peer-relay completion path was exercised. Because all submissions were incorrect, no provenance class carried a correct answer and no world was voided.

## Preregistered results

- **P0:** supported in this pilot: 0 committed TRACE/COMMIT captured a scanned objective fact.
- **P1:** not observed: the four C COMMITs persisted already-known facts only.
- **P2:** not observed and not testable: no committed trace existed.
- **P3:** not observed: no correct submission existed; environmental provenance was never carried by a correct answer.
- **P4:** unverified: no P1/P3 signal in either model family.

The result is therefore a bounded negative persistence observation under objective necessity, not evidence that environmental persistence lacks instrumental value. The scan mechanism was exercised in every condition (8 scans), the submission window bound as designed, and the models persisted facts — but only facts they already durably knew.

## Cost

For all 36 model calls: 36,471 prompt bytes, 2,616 generated bytes, 9,977 prompt tokens, 904 generated tokens, and 328.5 seconds wall time including eight model loads. Median request latency was approximately 1.83 seconds (range 1.19–14.11 seconds). A used 10,809 prompt bytes; B 13,638; C 12,024.

## Security and authority regression

All 36 parser-valid candidates passed the normal Gateway/kernel boundary. The pilot retained these invariants:

- generated intent is not committed state;
- visible reference is not authority;
- relevance/known value is not permission outside the current action contract;
- message and artifact text cannot mutate state;
- agent identity is not privilege;
- COMMIT is C-only and exact-value validated;
- private scans never persist into the submission window.

The deterministic tests included scan expiry, submission-window restriction, stale/malformed input rejection, fault rollback, idempotency, and replay. No Campfire files were modified.

## Evidence

Completed run: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_003_PILOT`

- result manifest: `867786a6e04e875f170a69516b4740ae04ad5574a9b60d6234a89c5af46dcbf5`
- planned manifest: `a7b6ded0d4e8b25949b29f271a828c1d106db36d2a7ac76e9ac80fd5400eefd9`
- validation receipt: `da5c983c9a814e555fb7b65a496eceb1abe3b30cc0450b643b32823637341034`
- scientific configuration SHA-256: `928aac4eb166c3c32f9318d9c4a9e136880f9b05a59ec9e60a054cbcdaacb884`
- final result: `result.json`
- canonical state/event database: `world.sqlite`
- CAS and per-tick observation/cost/load records: `cas/`, `tick-0.json` … `tick-3.json`, `observations.json`, `costs.json`, `loads.json`

The completed result was re-audited from the SQLite replay, event records, CAS references, and evidence hashes: **PASS**.
