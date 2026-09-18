# EXP-STIG-006 — REUSE-Necessary Stigmergic Read Path

## Status

**v1 PILOT COMPLETE.** The deterministic gate passed before model execution; the bounded pilot executed 36 real local-model opportunities across three model families. The world_state completion chain replicated identically to EXP-STIG-005 (P1o + P3 + P3o under the same serve-bind split), while the REUSE-necessary trace read path was never reached — no model wrote a trace. The preregistered stop-rule condition is met.

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
