# EXP-STIG-003 — Persistence-Necessary Retention

## Status

**v1 PILOT COMPLETE (bounded negative). v2 PILOT COMPLETE with a P1 event. v3 PILOT COMPLETE with P1 and P3 events.** Each deterministic gate passed before model execution; each bounded pilot executed 36 real local-model opportunities. v3 produced a voluntary committed COMMIT of a scanned objective fact and a correct terminal submission carrying environmental provenance — the first complete environmental persistence chain observed in this program. The preregistered stop-rule condition for a larger run is met; no larger run has been executed or scheduled.

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

The grounded-affordance system was retained with retention-specific conditions. Each opportunity compiled its action language from the current agent-visible state. INSPECT was afforded only before the submission window and only when no active scan covered the fact. In v1, TRACE/COMMIT admitted the union of persistent knowledge and active scans; in v2, TRACE binds only scan-covered facts. REUSE was restricted to exact visible committed trace IDs; SUBMIT to the terminal window only. Free-form SEND body and TRACE note remained unconstrained text subject to existing capacity validation; the v1 SUBMIT answer was free-form text while v2 constrains it to the objective answer skeleton.

The grammar hash, affordance descriptor, context/state version, and visible-reference set were stored with every attempt. The grammar narrowed proposals; RetentionStore/Gateway validation remained authoritative.

## v1 qualification

The qualification tested A/B/C initial states, active-scan states, controlled visible-trace states, stale trace references, the submission-window boundary, unknown fields, and trailing data. The capability qualification ran one full INSPECT → TRACE → REUSE → SUBMIT chain in each of B and C, verified correctness and `verified=True`, and replayed the store to the materialized state. Qualification passed.

The gate command was:

`python -m pytest tests/test_retention_persistence.py tests/test_instrumental_persistence.py tests/test_stigmergy.py tests/test_action_codec.py tests/test_action_affordance.py -q`

Result: **81 passed**. The qualification receipt is `E:/WORLD/AI_CACHE/evidence/EXP_STIG_003_PILOT/validation.json`.

## v1 real-model execution

- Model families: **2**
- Model artifacts: OLMo-2-0425-1B-Instruct Q8_0 (SHA-256 `4a180742…e33d6e6`) and Villanova-2B-2603 Q8_0 (SHA-256 `eb0865b1…f98577e`)
- Runtime: local llama.cpp `llama-server.exe`, SHA-256 `dd67a47d…6b22a5c`
- Persistent identities: 3
- Worlds: one each for A, B, C
- Ticks: 4; terminal submission window at tick 3
- Opportunities: 36 (12 per condition)
- Retries/fallback/repair: none
- Astra: not used

## v1 action funnel

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

## v1 treatment observations

**A:** 12/12 accepted; all three agents INSPECTed their missing fact at tick 0 (X17→F2, X29→F4, X43→F6), then four SEND and three WAIT. X17 and X43 SUBMITed at tick 3; both answers were incorrect. No trace or world mutation exists in A by construction.

**B:** 12/12 accepted; the same three tick-0 scans, then six SEND and one WAIT. TRACE was afforded once scans were active but was never selected; the visible trace set remained empty, so REUSE was never afforded. X17 and X43 SUBMITed at tick 3; both incorrect.

**C:** 12/12 accepted; X17 and X43 scanned their missing facts at tick 0; X29 did not scan. X17 COMMITed `F1=amber` at ticks 1 and 2 and X43 COMMITed `F5=onyx` at ticks 1 and 2 — all four committed facts were already in the actor's initial knowledge, not the scanned missing facts. Canonical world state ended as `{F1: amber, F5: onyx}`. X17 and X43 SUBMITed at tick 3; both incorrect.

All six SUBMIT payloads were the literal string `"objective answer, text at most 256 characters"` — the answer-field description echoed as the answer value rather than the scanned or known facts. No SEND body contained a scan-only value, so no peer-relay completion path was exercised. Because all submissions were incorrect, no provenance class carried a correct answer and no world was voided.

## v1 preregistered results

- **P0:** supported in this pilot: 0 committed TRACE/COMMIT captured a scanned objective fact.
- **P1:** not observed: the four C COMMITs persisted already-known facts only.
- **P2:** not observed and not testable: no committed trace existed.
- **P3:** not observed: no correct submission existed; environmental provenance was never carried by a correct answer.
- **P4:** unverified: no P1/P3 signal in either model family.

The result is therefore a bounded negative persistence observation under objective necessity, not evidence that environmental persistence lacks instrumental value. The scan mechanism was exercised in every condition (8 scans), the submission window bound as designed, and the models persisted facts — but only facts they already durably knew.

## v1 cost

For all 36 model calls: 36,471 prompt bytes, 2,616 generated bytes, 9,977 prompt tokens, 904 generated tokens, and 328.5 seconds wall time including eight model loads. Median request latency was approximately 1.83 seconds (range 1.19–14.11 seconds). A used 10,809 prompt bytes; B 13,638; C 12,024.

## v1 security and authority regression

All 36 parser-valid candidates passed the normal Gateway/kernel boundary. The pilot retained these invariants:

- generated intent is not committed state;
- visible reference is not authority;
- relevance/known value is not permission outside the current action contract;
- message and artifact text cannot mutate state;
- agent identity is not privilege;
- COMMIT is C-only and exact-value validated;
- private scans never persist into the submission window.

The deterministic tests included scan expiry, submission-window restriction, stale/malformed input rejection, fault rollback, idempotency, and replay. No Campfire files were modified.

## v1 evidence

Completed run: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_003_PILOT`

- result manifest: `867786a6e04e875f170a69516b4740ae04ad5574a9b60d6234a89c5af46dcbf5`
- planned manifest: `a7b6ded0d4e8b25949b29f271a828c1d106db36d2a7ac76e9ac80fd5400eefd9`
- validation receipt: `da5c983c9a814e555fb7b65a496eceb1abe3b30cc0450b643b32823637341034`
- scientific configuration SHA-256: `928aac4eb166c3c32f9318d9c4a9e136880f9b05a59ec9e60a054cbcdaacb884`
- final result: `result.json`
- canonical state/event database: `world.sqlite`
- CAS and per-tick observation/cost/load records: `cas/`, `tick-0.json` … `tick-3.json`, `observations.json`, `costs.json`, `loads.json`

The completed result was re-audited from the SQLite replay, event records, CAS references, and evidence hashes: **PASS**.

## Diagnostic probe (instrument check, not scientific evidence)

Between v1 and v2 a four-variant probe (`tools/exp_stig_003_probe.py`) asked whether the pinned models can emit real objective values at the submission window when the missing fact is fully visible. Fixture states placed X17 at tick 3 with `F2=cedar` present via committed world state (C), via a committed trace (B), or nowhere. Two answer surfaces were compared: the v1 free-text field and the v2 skeleton grammar.

- Free text with both facts visible in `world_state`: OLMo emitted the descriptor verbatim (`"objective answer, text at most 256 characters"`); Villanova WAITed. The v1 censoring is confirmed as an interface defect, not a content problem.
- Skeleton grammar: both models reliably produced the required `F1=<word>|F2=<word>` shape, but filled the slots with the literal template token `value` (OLMo 3/3, Villanova 1/1 SUBMITs) instead of binding `amber`/`cedar` from the visible state. Villanova WAITed in the other two skeleton variants.
- The probe therefore confirmed the skeleton is producible and removed the free-text censoring layer, while indicating that value binding under the descriptor template is unreliable. Probe records: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_003_PROBE2/probe-result.json` (an earlier probe run additionally exposed and fixed a grammar-quoting defect before v2 was frozen).

## v2 qualification

The v2 gate covered the same deterministic suite under the amended affordance semantics (TRACE scan-covered only, absent without a scan; SUBMIT skeleton descriptor and grammar), the capability chain, and the source freeze bound to `specs/experiments/EXP-STIG-003-v2.yaml` SHA-256 `9029a33c…5e584a`. Result: **81 passed**. The qualification receipt is `E:/WORLD/AI_CACHE/evidence/EXP_STIG_003_PILOT_V2/validation.json`.

## v2 real-model execution

Identical cohort, artifacts, runtime, generation policy, seed schedule and 36-opportunity bound as v1. No retries, fallback, repair, or Astra.

## v2 action funnel

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

Action counts were INSPECT 8, SEND 10, COMMIT 4, SUBMIT 8, and WAIT 6. No TRACE or REUSE was produced. Eight scans were created. One objective persistence act was committed.

## v2 treatment observations

**A:** 12/12 accepted; all three agents scanned at tick 0, then four SEND and two WAIT. All three agents SUBMITed at tick 3 — each emitted the objective template verbatim (`F1=value|F2=value` shape) and was incorrect.

**B:** 12/12 accepted; the same three tick-0 scans, then six SEND and one WAIT. TRACE was afforded while scans were active but never selected; no trace existed, so REUSE was never afforded. X17 and X43 SUBMITed at tick 3; both incorrect.

**C:** 12/12 accepted; X17 and X43 scanned at tick 0; X29 did not scan. X17 COMMITed `F1=amber` at ticks 1–2; X43 COMMITed `F5=onyx` at tick 1 and then **`F6=maple` at tick 2 — a voluntary committed persistence act on its own scanned missing objective fact**. Canonical world state ended as `{F1: amber, F5: onyx, F6: maple}`. All three agents SUBMITed at tick 3 with template echoes; all incorrect.

Notably, X43's tick-3 submission carried provenance `F6: environmental_world_state` — the committed value was present and correctly attributed at the window — but the submitted answer still echoed the template rather than binding `maple`. The environmental persistence chain therefore executed end-to-end for one agent while answer-value binding failed independently.

No SEND body contained a scan-only value; no peer-relay completion path was exercised. All submissions were incorrect, so no world was voided.

## v2 preregistered results

- **P0:** falsified in this pilot: 1 committed COMMIT captured a scanned objective fact.
- **P1:** supported: X43 (OLMo family) committed scanned `F6=maple` into world state at tick 2 in condition C.
- **P2:** not observed and not testable: no committed trace existed.
- **P3:** not observed: no correct submission existed. One submission carried environmental provenance but failed on answer-value binding.
- **P4:** not met: P1 occurred only under OLMo; P3 occurred under neither family.
- **pilot_signal:** true — the preregistered stop-rule condition for a larger run is satisfied by the P1 event. A larger run is authorized by the rule but has not been executed or scheduled.

The v2 result is the first observed voluntary persistence of an ephemeral observation in this program. It also isolates the remaining chain break: models persisted the scanned fact and the persisted value was visible at the window, yet submission produced the descriptor template rather than bound values.

## v2 cost

For all 36 model calls: 35,349 prompt bytes, 2,508 generated bytes, 9,733 prompt tokens, 914 generated tokens, and 158.6 seconds wall time including eight model loads. Median request latency was approximately 1.67 seconds (range 1.19–10.91 seconds). A used 10,794 prompt bytes; B 13,158; C 11,397.

## v2 security and authority regression

Same invariants as v1 held over all 36 committed actions; additionally, the v2 proposal surface restricted TRACE to scan-covered facts and the SUBMIT answer to the objective skeleton without weakening kernel authority. No Campfire files were modified.

## v2 evidence

Completed run: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_003_PILOT_V2`

- result manifest: `4fd490816e1c18434c914b1195a8387fcebf5bbf8236e49f96c6e5da54930b84`
- planned manifest: `cf9a9c921ccfcd898f7ba01bca9212193e3182ff90606e1ba0e92e57b07c48b4`
- validation receipt: `0a5186353f07b96bab1d3a6c627a866c744e8143c90f0c62710bdbf63dc70ebb`
- scientific configuration SHA-256: `9029a33c1b730f27186d4d97e9047b1f07b6b9cdb6fd2881782a94f7be5e584a`
- final result: `result.json`
- canonical state/event database: `world.sqlite`
- CAS and per-tick observation/cost/load records: `cas/`, `tick-0.json` … `tick-3.json`, `observations.json`, `costs.json`, `loads.json`

The completed result was re-audited from the SQLite replay, event records, CAS references, and evidence hashes: **PASS**.

## v3 amendment

v2 isolated the last chain break to answer-value binding: submissions emitted the literal template token `value`. v3 grammar-grounds each answer slot to the alternatives of fact values actually visible to the actor at tick 3 (persistent knowledge union committed trace values union, in C, committed world_state values). A value never persisted is un-emittable, so slot correctness and provenance coincide by construction; template tokens cannot be produced. Message text contributes no options, so under v3 the peer-relay route cannot produce a correct answer and is measured only for traffic; condition A is a pure negative control where correct submission is impossible by construction. World law, kernel validation, cohort, seeds, sizes and stop rules are unchanged.

A follow-up probe run before freezing validated the instrument: under v3 grammar OLMo bound `F1=amber|F2=cedar` correctly from both world_state and trace carriers, emitted `F1=amber|F2=amber` when `cedar` was absent from the option set (un-emittable), and Villanova selected real values with an incorrect fact mapping. Probe records: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_003_PROBE4/probe-result.json` (an earlier iteration exposed and fixed a value-quoting defect before v3 froze).

## v3 qualification

Same deterministic suite and source freeze bound to `specs/experiments/EXP-STIG-003-v3.yaml` SHA-256 `b6762869…4431a4`, with the window-state assertions updated for the value-grounded slots. Result: **81 passed**. The qualification receipt is `E:/WORLD/AI_CACHE/evidence/EXP_STIG_003_PILOT_V3/validation.json`.

## v3 real-model execution

Identical cohort, artifacts, runtime, generation policy, seed schedule and 36-opportunity bound as v1/v2. No retries, fallback, repair, or Astra.

## v3 action funnel

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

Action counts were INSPECT 8, SEND 10, COMMIT 4, SUBMIT 7, and WAIT 7. No TRACE or REUSE was produced. Eight scans were created. One objective persistence act and one environmental completion were committed.

## v3 treatment observations

**A:** 12/12 accepted; all three agents scanned at tick 0, then four SEND and three WAIT. X17 and X43 SUBMITed at tick 3, each filling both slots with their only visible value (`F1=amber|F2=amber`, `F5=onyx|F6=onyx`) — incorrect, and no missing-fact value was emittable by construction.

**B:** 12/12 accepted; three tick-0 scans, six SEND. TRACE was afforded while scans were active but never selected; no trace existed, so REUSE was never afforded. All three agents SUBMITed at tick 3 with knowledge-only values; all incorrect.

**C:** 12/12 accepted; X17 and X43 scanned at tick 0; X29 did not scan. X17 COMMITed `F1=amber` at ticks 1–2; X43 COMMITed `F5=onyx` at tick 1 and `F6=maple` at tick 2 — again a voluntary committed persistence act on its own scanned missing objective fact, replicating v2's P1 behavior under the same seed schedule. Canonical world state ended as `{F1: amber, F5: onyx, F6: maple}`. At tick 3 X17 submitted `F1=maple|F2=onyx` — real persisted values from the shared world state but mapped to the wrong facts — while **X43 submitted `F5=onyx|F6=maple`, a correct answer whose missing fact `F6` carried `environmental_world_state` provenance**.

## v3 preregistered results

- **P0:** falsified: 1 committed COMMIT captured a scanned objective fact.
- **P1:** supported: X43 (OLMo) committed scanned `F6=maple` into world state at tick 2 in condition C — replicating the v2 P1 event under identical assignment and seed schedule.
- **P2:** not observed and not testable: no committed trace existed.
- **P3:** supported: X43's tick-3 submission was correct and its missing fact `F6` carried `environmental_world_state` provenance, established mechanically from recorded state.
- **P4:** not met: P1 and P3 occurred only under OLMo; Villanova produced no persistence act.
- **pilot_signal:** true — the stop-rule condition for a larger run is satisfied; none has been executed or scheduled.

v3 is the first completed environmental persistence chain in this program: scan → voluntary COMMIT into world state → correct windowed submission with mechanically audited environmental provenance. The remaining gaps are channel selection (TRACE never chosen; world_state COMMIT carried the chain), reuse (no trace existed to reuse), and cross-family replication (Villanova produced none).

## v3 cost

For all 36 model calls: 35,574 prompt bytes, 2,474 generated bytes, 9,798 prompt tokens, 921 generated tokens, and 234.4 seconds wall time including eight model loads. Median request latency was approximately 1.61 seconds (range 1.20–10.19 seconds). A used 10,851 prompt bytes; B 13,215; C 11,508.

## v3 security and authority regression

Same invariants as v1/v2 held over all 36 committed actions. The v3 proposal surface additionally made unpersisted values un-emittable in SUBMIT without weakening kernel authority; kernel validation, provenance classification and replay semantics are unchanged. No Campfire files were modified.

## v3 evidence

Completed run: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_003_PILOT_V3`

- result manifest: `228dbc3e4e0a2830f858f0a9b799e2a54fba61c0082bd4d227506c5c8e0938eb`
- planned manifest: `f646e9a12e4af41170ef2e7f43eab4fb7aaaadc627cea214a7935a5d7a8c2aff`
- validation receipt: `983c5f9375c7b1d5e3173d81e6801ef673dc781af97e2a4b16a978d2f8bea377`
- scientific configuration SHA-256: `b6762869733112df9fdde39a5b86701dfbebf47eeeda5d4138eca4fb7e4431a4`
- final result: `result.json`
- canonical state/event database: `world.sqlite`
- CAS and per-tick observation/cost/load records: `cas/`, `tick-0.json` … `tick-3.json`, `observations.json`, `costs.json`, `loads.json`

The completed result was re-audited from the SQLite replay, event records, CAS references, and evidence hashes: **PASS**.
