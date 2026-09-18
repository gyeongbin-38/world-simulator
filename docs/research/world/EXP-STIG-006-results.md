# EXP-STIG-006 — REUSE-Necessary Stigmergic Read Path

## Status

**v1 LARGER RUN COMPLETE.** The deterministic gate passed before model execution; the bounded pilot executed 36 real local-model opportunities and the preregistered stop rule authorized the larger run, which executed 108 opportunities under the Latin-square cohort assignment `[[0,1,2],[1,2,0],[2,0,1]]`. The world_state completion chain replicated again (P1s + P1o + P3 + P3o under the same OLMo-serve / SmolLM3-bind split). Under the REUSE-necessary law the trace read path was still never completed: TRACE was selected once — the first selection under this law — but was rejected for a descriptor-echo value, and REUSE was never selected.

This experiment is separate from EXP-STIG-001/002/003/004/005. Those records remain unchanged.

## Objective and preregistration

EXP-STIG-005's single TRACE completion exposed that committed trace values entered window options directly, making REUSE structurally pointless. `specs/experiments/EXP-STIG-006-v1.yaml` froze the identical world law minus one change: raw trace values no longer enter submission-window answer options — a trace's value reaches the grammar only through REUSE-internalized knowledge. World_state values (C) still enter directly. Same three-family cohort and pilot assignment `[[2, 0, 1]]`. Outcomes: P0, P1s, P1o, P2 (primary: whether the trace read path is used at all), P3, P3o, P4. The pilot is bounded at 36 opportunities.

## Pilot qualification

Same deterministic suite and source freeze: 95 pytest tests, affordance qualification, and the cross-agent capability fixture — which under the new law exercises the full INSPECT → TRACE → foreign REUSE → SUBMIT path in B and the unchanged COMMIT path in C. Result: **95 passed**. Receipt: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_006_PILOT/validation.json`.

## Pilot execution

- Model families: **3** — OLMo Q8_0, Villanova Q8_0, SmolLM3 Q4_K_M, each 12 opportunities
- Worlds: 1 per condition; ticks: 4; terminal submission window at tick 3
- Opportunities: 36 (12 per condition)
- Retries/fallback/repair: none; Astra: not used

## Pilot action funnel

| stage | count |
|---|---:|
| generation opportunities | 36 |
| completed generations | 36 |
| strict parser-valid candidates | 35 |
| affordance-valid candidates | 35 |
| Gateway-valid intents | 33 |
| committed actions | 33 |
| protocol rejection | 1 |
| affordance rejection | 0 |
| semantic rejection | 2 |
| kernel conflict | 0 |
| timeout | 0 |
| model-load failure | 0 |
| transport/runtime failure | 0 |

Same rejection profile as EXP-STIG-005: one Villanova unterminated JSON (B tick 1), two Villanova COMMIT attempts with descriptor-echo values (C ticks 0–1).

Action counts: INSPECT 5, SEND 14, COMMIT 4, SUBMIT 9, WAIT 3. **TRACE 0, REUSE 0.**

## Pilot treatment observations

**A:** all committed; X29 (OLMo) and X43 (Villanova) cross-scanned; generic SENDs; all submissions incorrect — negative control holds.

**B:** OLMo and Villanova cross-scanned (X29→F2, X43→F6), but no agent wrote a trace — the REUSE-necessary read path was never reached. This is the first measurement of TRACE selection when it is the sole channel for both self and peer benefit: still zero.

**C:** identical completion to EXP-STIG-005: X29 (OLMo) scanned F2 and committed `F2=cedar` (t1) plus non-objective `F3` (t2); X17 (SmolLM3) submitted `F1=amber|F2=cedar` — correct with `F2: environmental_world_state` provenance. Villanova's two COMMIT attempts rejected.

## Pilot preregistered results

- **P0:** falsified: one committed COMMIT captured a scanned fact.
- **P1s:** not observed: X43 (Villanova) attempted but never committed.
- **P1o:** supported: OLMo committed scanned `F2=cedar` needed by X17.
- **P2:** not observed: no REUSE occurred — and none could, since no trace was written. The read path is unreachable while trace-write is absent.
- **P3:** supported: one correct submission with environmental provenance.
- **P3o:** supported: X17/SmolLM3 correct dependent submission — the same serve-bind chain as EXP-STIG-005.
- **P4:** not met: P1o under OLMo only.
- **pilot_signal:** true (P1o + P3o events).

The pilot answers the motivating question negatively but informatively: the stigmergic read path cannot be measured because the write side (TRACE) does not activate even under doubled necessity — the sole channel for both self and peer benefit. The bottleneck is trace-writing, not internalization. Combined with EXP-STIG-005's 1/108 TRACE rate, trace-writing is rare but possible under OLMo; whether foreign REUSE would follow a written trace remains untested at the behavioral level.

## Pilot cost

For all 36 model calls: 44,073 prompt bytes, 952 generated tokens, 12,439 prompt tokens, and 909.5 seconds wall time including 12 model loads. Median request latency approximately 4.4 seconds.

## Pilot security and authority regression

Same invariants held over all 33 committed actions: proposals only, deterministic validated commit boundary, same-tick isolation, agent-scoped visibility, CAS-backed artifacts, replay-verified metrics. The 3 rejected proposals were recorded as events, never committed. No Campfire files were modified.

## Pilot evidence

Completed run: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_006_PILOT`

- result manifest: `ef82402cfab197940f292f10846605352eeb38d226c61414fb7d934709711d93`
- planned manifest: `91e949e03ece4b2b82df3721530a50b3fbc0c97fb28dbc8ff7850bdef6862f82`
- validation receipt: `f4eddfe5ea261bb674da6161489d535ee3ea4217487b5cfc2a7eb30f7b3ea6bb`
- scientific configuration SHA-256: `e37a2bd72acaf88680ee471cf39659de64d999e5d3aa6cdf44c3afee03af6dd7`
- final result: `result.json`
- canonical state/event database: `world.sqlite`
- CAS and per-tick observation/cost/load records: `cas/`, `tick-0.json` … `tick-3.json`, `observations.json`, `costs.json`, `loads.json`

The completed result was re-audited from the SQLite replay, event records, CAS references, and evidence hashes: **PASS**.

## Larger run

The preregistered stop rule was met by the pilot (P1o + P3o events), authorizing the larger run. `specs/experiments/EXP-STIG-006-run-v1.yaml` froze 3 worlds per condition with the Latin-square cohort assignment `[[0,1,2],[1,2,0],[2,0,1]]` — each family serves each role once per condition — bound by `specs/experiments/EXP-STIG-006-execution-run.yaml` (`scientific_config_sha256: d81a54b9…`, seed tag `EXP-STIG-006-RUN`, `large_run_authorized: true`). Gate before execution: **95 passed**, affordance qualification PASS. 108 generation opportunities, no retries/repair/fallback/Astra.

## Run action funnel

| stage | count |
|---|---:|
| generation opportunities | 108 |
| completed generations | 108 |
| strict parser-valid candidates | 106 |
| affordance-valid candidates | 106 |
| Gateway-valid intents | 102 |
| committed actions | 102 |
| protocol rejection | 2 |
| affordance rejection | 0 |
| semantic rejection | 4 |
| kernel conflict | 0 |
| timeout | 0 |
| model-load failure | 0 |
| transport/runtime failure | 0 |

Rejections: two Villanova unterminated-JSON outputs (B-0 t1 X29, B-2 t1 X43); four semantic rejections — three Villanova COMMITs with descriptor-echo values (C-0 t2 X29 `F3`, C-2 t0/t1 X43 `F5`) and **one OLMo TRACE with a descriptor-echo value** (B-1 t2 X43 `F6`).

Action counts (committed): INSPECT 15, SEND 43, COMMIT 9, SUBMIT 27, WAIT 11, TRACE 0, REUSE 0. TRACE was *selected* once (the rejected attempt above) — the first TRACE selection under the REUSE-necessary law — but no trace was ever committed, so no trace existed for REUSE to internalize.

## Run per-world summary

| world | actions | persistence | correct |
|---|---|---|---|
| A-0 | INSPECT 2, SEND 6, SUBMIT 3, WAIT 1 | none | 0 |
| A-1 | INSPECT 2, SEND 5, SUBMIT 3, WAIT 2 | none | 0 |
| A-2 | INSPECT 2, SEND 5, SUBMIT 3, WAIT 2 | none | 0 |
| B-0 | INSPECT 2, SEND 6, SUBMIT 3 | none | 0 |
| B-1 | INSPECT 2, SEND 6, SUBMIT 3 | TRACE attempt rejected | 0 |
| B-2 | INSPECT 2, SEND 6, SUBMIT 3 | none | 0 |
| C-0 | COMMIT 2, INSPECT 1, SEND 3, SUBMIT 3, WAIT 2 | X17 `F4=umber` (other) | 0 |
| C-1 | COMMIT 2, INSPECT 1, SEND 3, SUBMIT 3, WAIT 3 | X43 `F6=maple` (self) | 1 |
| C-2 | COMMIT 2, INSPECT 1, SEND 3, SUBMIT 3, WAIT 1 | X29 `F2=cedar` (other) + `F3` (base) | 1 |

Committed persistence (5 acts, all OLMo):

- C-0 t1/t2 X17 (OLMo): `COMMIT F4=umber` — scanned fact needed by X29; X29's submission carried `F4: environmental_world_state` provenance but was incorrect.
- C-1 t1/t2 X43 (OLMo): `COMMIT F6=maple` — self-serving; X43 then submitted correctly (self chain complete).
- C-2 t1 X29 (OLMo): `COMMIT F2=cedar` — scanned fact needed by X17, plus base-fact `F3=violet` at t2; X17's submission was correct (dependent chain complete).

## Run model-family split

| family | INSPECT | SEND | SUBMIT | COMMIT | WAIT | TRACE/REUSE | committed persistence |
|---|---:|---:|---:|---:|---:|---:|---|
| OLMo | 9 | 11 | 9 | 6 | 0 | 1 TRACE attempt / 0 | 5 (all) |
| Villanova | 6 | 5 | 9 | 0 | 11 | 0/0 | 0 |
| SmolLM3 | 0 | 27 | 9 | 0 | 0 | 0/0 | 0 |

Same capability split as EXP-STIG-005, now under three full rotations: OLMo is the sole persister (self and other-serving, both directions), SmolLM3 is the binder (never scanned, never persisted, correct when served), Villanova shows intent-without-binding (scans, attempts COMMIT, descriptor-echo values rejected; also both protocol rejections).

## Run preregistered results

- **P0:** falsified — committed COMMITs captured scanned facts.
- **P1s:** supported — X43 (OLMo) committed scanned `F6=maple` in C-1.
- **P1o:** supported — X17 committed `F4=umber` for X29 (C-0); X29 committed `F2=cedar` for X17 (C-2). Both directions, OLMo only.
- **P2:** not observed — REUSE was never selected. TRACE was selected once (B-1, OLMo) but rejected for a descriptor-echo value, so no committed trace ever existed to internalize.
- **P3:** supported — two correct submissions with environmental provenance (C-1 X43/OLMo self chain; C-2 X17/SmolLM3 dependent chain).
- **P3o:** supported — X17/SmolLM3 bound `F2=cedar` served by X29/OLMo (C-2), `environmental_world_state` provenance. Third dependent completion across the program (EXP-STIG-005 pilot + run, now 006).
- **P4:** not met — all committed persistence under OLMo only.

## Run interpretation

The REUSE-necessary law answered its question with a sharper negative than the pilot: even when internalization is the *only* way a trace value can reach an answer, the read path still cannot be measured because the write side does not activate — one TRACE selection in 108 opportunities (plus one in the pilot makes two selections in the entire program history), rejected on the same fact→value binding failure seen elsewhere. The bottleneck is confirmed upstream of REUSE: it is trace *writing*, specifically value-binding inside the write action.

Meanwhile the world_state path replicated for a third consecutive design: the OLMo-serve / SmolLM3-bind division of labor completed a dependent chain in C-2 and a self-serving chain in C-1. The capability split — OLMo writes, SmolLM3 binds, Villanova intends without binding — is now stable across pilot + run under all three Latin-square rotations.

## Run cost

108 requests: 132,251 prompt bytes, 2,724 generated tokens, 37,461 prompt tokens, 1,520.0 s wall time including 12 model loads (~14.1 s/request median including loads).

## Run security and authority regression

Same invariants held over all 102 committed actions: proposals only, deterministic validated commit boundary, same-tick isolation, agent-scoped visibility, CAS-backed artifacts, replay-verified metrics. All 6 rejected proposals were recorded as events, never committed. The REUSE-necessary window law was verified by the capability fixture pre-execution.

## Run evidence

Completed run: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_006_RUN`

- result manifest: `6e0cbb64fddc0648538d91781085313ed90d1cc6127a0940805ec01c858db196`
- planned manifest: `e04849ba032ae45319506badd6a863843bb39fa804b3c355328b8b367056fddb`
- audit: **PASS** (SQLite replay, event records, CAS references, evidence hashes)
- canonical state/event database: `world.sqlite`; per-tick observations/costs/loads sealed in `result.json` evidence hashes
