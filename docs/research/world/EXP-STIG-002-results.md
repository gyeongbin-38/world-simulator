# EXP-STIG-002 — Instrumental Persistence

## Status

**PILOT COMPLETE; no large run authorized.** The deterministic/fault/replay and grounded-affordance gate passed before model execution. The bounded pilot executed 18 real local-model opportunities. The preregistered stop rule prevented a larger run because no spontaneous committed TRACE occurred.

This experiment is separate from EXP-STIG-001 R2/R3/R4. Those records remain unchanged. R2 remains protocol-censored and R3 remains the syntactically constrained but semantically ungrounded interface experiment.

## Objective and preregistration

The pilot tested whether persistent information has instrumental value in a small objectively checkable environment. Three persistent identities (X17, X29, X43) each had an overlapping two-fact objective and initially knew one of the required facts. INSPECT costs one exploration unit; SUBMIT would have been objectively scored; TRACE/REUSE were available only in B/C when grounded by visible committed traces; C also exposed grounded COMMIT.

Treatments were fixed:

- **A — MESSAGE ONLY:** WAIT, SEND, INSPECT, SUBMIT.
- **B — PERSISTENT TRACE:** A plus TRACE and grounded REUSE.
- **C — CAUSAL WORLD:** B plus grounded COMMIT of a known fact.

No traces were seeded into the primary worlds. No action, contribution, collaboration, or return was requested.

Preregistered outcomes were P0 (no bootstrap), P1 (bootstrap), P2 (later reuse), P3 (measurable objective benefit), and P4 (replication across heterogeneous models/worlds). P3 requires an actual trace signal; P4 requires replication beyond this one-world-per-condition pilot.

## Affordance boundary

The R4 grounded-affordance system was retained. Each opportunity compiled its action language from the current agent-visible state. REUSE was absent when no trace was visible and, when present, was restricted to exact visible trace IDs. INSPECT was removed after the actor knew all objective facts. C COMMIT was restricted to known fact IDs and exact known values. Free-form SEND body, TRACE note, and SUBMIT answer remained unconstrained text subject to existing capacity validation.

The grammar hash, affordance descriptor, context/state version, and visible-reference set were stored with every attempt. The grammar narrowed proposals; InstrumentalStore/Gateway validation remained authoritative.

## Qualification

The qualification tested A initial, B/C initial, controlled visible-trace states, an exhausted objective state, stale trace references, unknown fields, and trailing data. It also exercised a controlled REUSE and C COMMIT capability fixture. Qualification passed.

The gate command was:

`python -m pytest tests/test_instrumental_persistence.py tests/test_stigmergy.py tests/test_action_codec.py tests/test_action_affordance.py -q`

Result: **68 passed**. The qualification receipt is `E:/WORLD/AI_CACHE/evidence/EXP_STIG_002_PILOT_RUN4/validation.json`.

## Real-model execution

- Model families: **2**
- Model artifacts: OLMo-2-0425-1B-Instruct Q8_0 (SHA-256 `4a180742…e33d6e6`) and Villanova-2B-2603 Q8_0 (SHA-256 `eb0865b1…f98577e`)
- Runtime: local llama.cpp `llama-server.exe`, SHA-256 `dd67a47d…6b22a5c`
- Persistent identities: 3
- Worlds: one each for A, B, C
- Ticks: 2
- Opportunities: 18 (6 per condition)
- Retries/fallback/repair: none
- Astra: not used

The first attempted output directory (RUN3) stopped before model generation because of an adapter argument error and is not scientific evidence. RUN4 is the sole completed pilot record.

## Action funnel

Across the 18 completed generations:

| stage | count |
|---|---:|
| generation opportunities | 18 |
| completed generations | 18 |
| strict parser-valid candidates | 18 |
| affordance-valid candidates | 18 |
| Gateway-valid intents | 18 |
| committed actions | 18 |
| protocol rejection | 0 |
| affordance rejection | 0 |
| semantic rejection | 0 |
| kernel conflict | 0 |
| timeout | 0 |
| model-load failure | 0 |
| transport/runtime failure | 0 |

Action counts were INSPECT 6, SEND 6, COMMIT 4, and WAIT 2. No TRACE, REUSE, or SUBMIT was produced.

## Treatment observations

**A:** 6/6 accepted; three INSPECT actions (one per agent) at tick 0 and three SEND actions at tick 1. Exploration cost was one per agent. No persistent trace, submission, or world mutation existed.

**B:** 6/6 accepted; the same action pattern as A. No trace bootstrap occurred, so there were no REUSE opportunities and no trace reuse. The visible trace set remained empty.

**C:** 6/6 accepted; X17 and X43 each COMMITed a known fact at tick 0, producing canonical world state `F1=amber` and `F2=cedar`. Their tick-1 COMMITs were accepted no-ops (`changed=false`); X29 WAITed on both ticks. No trace was created. There were no SUBMIT actions, so objective answer accuracy was not observed.

Within each A and B world, each of the three missing facts was inspected once. The aggregate evidence contains three repeated fact inspections only because A and B are separate matched worlds; it is not evidence of within-world duplicate exploration.

## Instrumental persistence results

- **P0:** supported in this pilot: 0 spontaneous committed TRACE bootstraps.
- **P1:** not observed.
- **P2:** not testable: no committed trace existed.
- **P3:** not testable under the preregistered condition because no trace signal and no scored SUBMIT outcomes occurred. C showed two canonical state mutations, but they were model-selected COMMIT actions and did not create a trace/reuse comparison.
- **P4:** unverified: one world per condition and no bootstrap signal do not provide world replication.

The result is therefore a bounded negative bootstrap observation, not evidence that persistent traces lack instrumental value.

## Cost

For all 18 model calls: 14,900 prompt bytes, 1,159 generated bytes, 4,226 prompt tokens, 433 generated tokens, and 33.075 seconds summed request time. Median request latency was approximately 1.506 seconds (range 1.034–3.634 seconds). A used 4,362 prompt bytes; B 5,025; C 5,513. The compact grounded interface remained executable without history replay.

## Security and authority regression

All 18 parser-valid candidates still passed the normal Gateway/kernel boundary. The pilot retained these invariants:

- generated intent is not committed state;
- visible reference is not authority;
- relevance/known value is not permission outside the current action contract;
- message and artifact text cannot mutate state;
- agent identity is not privilege;
- COMMIT is C-only and exact-value validated.

The deterministic tests included stale/malformed input rejection and fault rollback/idempotency. The full repository suite after the change was **646 passed, 69 skipped**. No Campfire files were modified.

## Evidence

Completed run: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_002_PILOT_RUN4`

- result manifest: `8732d3419be3746d0c57e79a3866fd1477de2bce57261a7c6fe38ae962849708`
- planned manifest: `0bf4b755f6cdc5ebc960407800f14c03fff516935df4c0f14b954c0e9dc9bf81`
- validation receipt: `b626d68081f5af30594f5a0dbaea5c60868c889864a2e0b57699f54947994ff6`
- final result: `result.json`
- canonical state/event database: `world.sqlite`
- CAS and per-tick observation/cost/load records: `cas/`, `tick-0.json`, `tick-1.json`, `observations.json`, `costs.json`, `loads.json`

The completed result was re-audited from the SQLite replay, event records, CAS references, and evidence hashes: **PASS**.
