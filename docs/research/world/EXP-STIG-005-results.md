# EXP-STIG-005 — Cross-Family Stigmergic Persistence Cohort

## Status

**v1 PILOT COMPLETE with P1o, P3, and P3o events — the first completed cross-agent stigmergic chain in this program.** The deterministic gate passed before model execution; the bounded pilot executed 36 real local-model opportunities across three model families. The preregistered stop-rule condition is met; no larger run has been executed or scheduled.

This experiment is separate from EXP-STIG-001/002/003/004. Those records remain unchanged.

## Objective and preregistration

EXP-STIG-004 found other-serving environmental persistence replicating under OLMo while the needer's fact-to-value binding failed in every world for both cohort families. `specs/experiments/EXP-STIG-005-v1.yaml` froze a three-family cohort under the identical world law before any model inference: OLMo-2-0425-1B-Instruct Q8_0 (index 0), Villanova-2B-2603 Q8_0 (index 1), SmolLM3-3B Q4_K_M (index 2). Pilot assignment `[[2, 0, 1]]` places SmolLM3 as X17 (serves F4→X29, needs F2), OLMo as X29 (serves F2→X17, needs F4), and Villanova as X43 (self-serving arm). Outcomes: P0, P1s, P1o, P2, P3, P3o, P4 (P1o under at least two families). The pilot is bounded at 36 opportunities; a larger run is authorized only on a P1o, P3/P3o, or other justified signal in the sealed receipt.

## Pilot qualification

The deterministic gate ran before model execution with all bound source files hashed and sealed: 92 pytest tests, the affordance qualification surface (cross-scan INSPECT, peer-objective visibility, TRACE scan-coverage, submission-window value grounding), and the cross-agent capability fixture for both persistent treatments. Result: **92 passed**. Receipt: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_005_PILOT/validation.json`.

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

The single protocol rejection was Villanova (X43, B tick 1) emitting unterminated JSON. Both semantic rejections were Villanova COMMIT attempts (C ticks 0–1) whose value was descriptor placeholder text — the same intent-without-binding profile as EXP-STIG-004, now in the self-serving role.

Action counts: INSPECT 5, SEND 14, COMMIT 4, SUBMIT 9, WAIT 3. TRACE 0 and REUSE 0 across all opportunities.

## Pilot treatment observations

**A:** all committed; X29 (OLMo) and X43 (Villanova) cross-scanned at tick 0; SmolLM3 did not scan; SEND bodies were generic greetings; all three submissions incorrect (knowledge-value echoes) — negative control holds.

**B:** all committed except the Villanova JSON failure; same cross-scans, generic SENDs; TRACE never selected despite sole-channel necessity; all submissions incorrect.

**C:** the complete dependent chain closed for the first time. X29 (OLMo) scanned F2 at tick 0 and committed `F2=cedar` at tick 1 — other-serving persistence for X17 (replicating its EXP-STIG-004 serving role in the reverse direction) — plus a non-objective `F3` commit at tick 2. At tick 3, **X17 (SmolLM3) submitted `F1=amber|F2=cedar` — correct, with `F2: environmental_world_state` provenance**. X29 and X43 submitted incorrectly (F4 and F6 unexplained — neither was ever persisted). Villanova's two COMMIT attempts carried descriptor-echo values and were kernel-rejected; it never scanned F6 in C.

## Pilot preregistered results

- **P0:** falsified: one committed COMMIT captured a scanned fact.
- **P1s:** not observed: X43 (Villanova) attempted but never committed a scanned fact.
- **P1o:** supported: OLMo committed scanned `F2=cedar` needed by X17.
- **P2:** not observed: no committed trace existed.
- **P3:** supported: one correct submission with environmental provenance.
- **P3o:** supported: the correct submission was X17's dependent objective — **the first completed cross-agent stigmergic chain** (OLMo persists → SmolLM3 binds).
- **P4:** not met: P1o occurred under OLMo only; SmolLM3 never scanned its serveable fact and Villanova produced no committed persistence act.
- **pilot_signal:** true.

The pilot answers both motivating questions directionally: the dissociation replicates as a capability split — serving (scan-and-persist for a peer) occurred under OLMo, while fact-to-value binding at the window succeeded under SmolLM3 — and the complete chain is achievable by the extended cohort. One world per condition bounds all claims.

## Pilot cost

For all 36 model calls: 41,037 prompt bytes, 938 generated tokens, 11,775 prompt tokens, and 671.5 seconds wall time including 12 model loads. Median request latency approximately 4.3 seconds.

## Pilot security and authority regression

Same invariants held over all 33 committed actions: proposals only, deterministic validated commit boundary, same-tick isolation, agent-scoped visibility, CAS-backed artifacts, replay-verified metrics. The 3 rejected proposals were recorded as events, never committed. No Campfire files were modified.

## Pilot evidence

Completed run: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_005_PILOT`

- result manifest: `2255ddb5f05d7ddee79b9a11e542ed9b43af94f604f580ca51d9819bcef55410`
- planned manifest: `c5689a0f6e5c7b93a42d0c0f70a119db2a7c3301bfed632760afaad7699d5b0b`
- validation receipt: `c189dc74b0fa9e428c5161552828a442371a2aac4037a3db7573da3861ac7d7e`
- scientific configuration SHA-256: `9dc96d46609269034f8c2fc5f716e6766f335a19f9c331c9214597a08bfe8b2f`
- final result: `result.json`
- canonical state/event database: `world.sqlite`
- CAS and per-tick observation/cost/load records: `cas/`, `tick-0.json` … `tick-3.json`, `observations.json`, `costs.json`, `loads.json`

The completed result was re-audited from the SQLite replay, event records, CAS references, and evidence hashes: **PASS**.
