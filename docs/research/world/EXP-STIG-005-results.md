# EXP-STIG-005 — Cross-Family Stigmergic Persistence Cohort

## Status

**v1 PILOT COMPLETE with P1o, P3, and P3o events — the first completed cross-agent stigmergic chain in this program. AUTHORIZED LARGER RUN (3 worlds per condition, 108 opportunities, Latin-square assignment) COMPLETE.** The deterministic gate passed before each model execution. The larger run replicated the completed dependent chain under the extended cohort (OLMo persists → SmolLM3 binds), produced the first TRACE-channel completion ever observed, and showed P1o only under OLMo — P4 remains unmet.

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

## Larger-run preregistration

The v1 pilot's P1o and P3o events authorized a larger run under the preregistered stop rule. `specs/experiments/EXP-STIG-005-run-v1.yaml` fixed the run before any inference: 3 worlds per condition (108 opportunities), unchanged v1 world law, a fresh seed schedule (`SHA256(EXP-STIG-005-RUN,condition,world,tick,actor)`), and a Latin-square assignment `[[0,1,2],[1,2,0],[2,0,1]]` covering each family in each role once per condition. Same P0/P1s/P1o/P2/P3/P3o/P4 definitions plus the secondary TRACE-frequency measurement. The run is a single replication study; no further size increase is implied.

## Larger-run qualification

Same deterministic suite and source freeze bound to `specs/experiments/EXP-STIG-005-run-v1.yaml` SHA-256 `ae05466c56273837bede0a0e74d48cedf74e3e437fb82ac3924ad15859a3b579`. Result: **92 passed**. Receipt: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_005_RUN/validation.json`.

## Larger-run execution

- Model families: **3** (same pinned artifacts and llama.cpp runtime; SmolLM3 is Q4_K_M — disclosed confound)
- Worlds: 3 per condition (9 run IDs `EXP-STIG-005-RUN-{A,B,C}-{0..2}`)
- Ticks: 4; terminal submission window at tick 3
- Opportunities: 108 (36 per condition); 36 jobs per family
- Retries/fallback/repair: none; Astra: not used

## Larger-run action funnel

| stage | count |
|---|---:|
| generation opportunities | 108 |
| completed generations | 108 |
| strict parser-valid candidates | 107 |
| affordance-valid candidates | 107 |
| Gateway-valid intents | 101 |
| committed actions | 101 |
| protocol rejection | 1 |
| affordance rejection | 0 |
| semantic rejection | 6 |
| kernel conflict | 0 |
| timeout | 0 |
| model-load failure | 0 |
| transport/runtime failure | 0 |

All 7 rejections were Villanova: one unterminated JSON (B-2) and six COMMIT attempts whose value was descriptor placeholder text (C worlds). The intent-without-binding profile replicated exactly.

Action counts: INSPECT 15, SEND 43, COMMIT 12, TRACE 1, SUBMIT 27, WAIT 9. REUSE 0. **TRACE 1/108 — the channel's first-ever selection** (X43/OLMo, B-1, capturing scanned F6).

## Larger-run treatment observations

**A:** all committed; scanning split by family — OLMo and Villanova scanned in every world, SmolLM3 never scanned; SEND traffic heaviest of any run but bodies generic; all 9 submissions incorrect — negative control holds.

**B:** **first TRACE completion in program history**: X43 (OLMo, B-1) scanned F6 at tick 0, committed it as a trace at tick 2, and submitted `F5=onyx|F6=maple` at tick 3 — correct with `environmental_trace` provenance (trace values enter the window grammar without REUSE). TRACE remained unselected in B-0/B-2 and in every mutual-dependence serving role. One Villanova JSON failure (B-2).

**C:** other-serving persistence under OLMo in both directions: X17 committed `F4=umber` for X29 (C-0) and X29 committed `F2=cedar` for X17 (C-2); self-serving `F6=maple` commits by X43/OLMo (C-1). **P3o replicated**: X17 (SmolLM3, C-2) submitted `F1=amber|F2=cedar` — correct, `F2: environmental_world_state` provenance, matching the pilot's chain exactly. X43 (OLMo, C-1) also completed self-serving (`F6: environmental_world_state`). In C-0 the delivered `F4=umber` entered X29's (SmolLM3) grammar with environmental provenance but the answer was still incorrect — SmolLM3's binding is imperfect, not guaranteed. Villanova attempted COMMIT in every C world it served (6 rejections, descriptor-echo values) and produced no committed persistence act.

Per-family scan totals: OLMo 9, Villanova 6, SmolLM3 0. Villanova scans when no COMMIT exists (A/B) but switches to unscanned COMMIT attempts in C — intent without acquisition.

## Larger-run preregistered results

- **P0:** falsified: 6 committed TRACE/COMMIT events captured scanned facts (3 self-serving: F6 ×2 commits + F6 trace; 3 other-serving: F4 ×2 commits + F2 commit).
- **P1s:** supported under OLMo (F6 commits C-1, F6 trace B-1); Villanova's self-serving attempts all rejected.
- **P1o:** supported and replicated under OLMo in both serving directions (F4→X29 in C-0, F2→X17 in C-2).
- **P2:** not observed: no REUSE of any trace.
- **P3:** supported: 3 correct submissions, all with environmental provenance (1 `environmental_trace`, 2 `environmental_world_state`).
- **P3o:** supported and replicated: X17/SmolLM3 correct dependent submission in C-2 — same serve-bind split as the pilot (OLMo persists, SmolLM3 binds).
- **P4:** not met: P1o under OLMo only; SmolLM3 never scanned (0/15 scans) and Villanova never committed.
- **TRACE channel (secondary):** 1 selection in 108 opportunities — first nonzero measurement; still near-zero, but the channel is demonstrably usable end-to-end when chosen.
- **pilot_signal:** true (redundant under the already-authorized run).

The cohort result sharpens the dissociation into three distinct capability profiles: OLMo scans and persists (self and other-serving, both channels) but binds inconsistently; SmolLM3 never scans yet binds well enough to close the chain when served; Villanova shows persistence intent with systematic binding failure and zero committed acts. Every correct submission across the run was environmental-provenance-backed — no unexplained or relay answers — and all provenance classifications were mechanical.

## Larger-run cost

For all 108 model calls: 125,338 prompt bytes, 7,565 generated bytes, 36,025 prompt tokens, 2,771 generated tokens, and 1673.8 seconds wall time including 12 model loads (zero load failures). Median request latency approximately 5.66 seconds.

## Larger-run security and authority regression

Same invariants held over all 101 committed actions: proposals only, deterministic validated commit boundary, same-tick isolation, agent-scoped visibility (scans private; only the objective board and sensor map public), CAS-backed artifacts, replay-verified metrics. The 7 rejected proposals were recorded as events, never committed. No Campfire files were modified.

## Larger-run evidence

Completed run: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_005_RUN`

- result manifest: `ea16d9e424e03482118f29c59b71d773a215f54fd1d83a267f48bcc33fd695d1`
- planned manifest: `ae1cbf711207bca7522bdb30df368dbb466a1481ade7d48ec19a42718fb5fdfa`
- validation receipt: `75d9533de9e1457e8c1cb662a1a9363ff06fd5341d685679b439a652782658b2`
- scientific configuration SHA-256: `ae05466c56273837bede0a0e74d48cedf74e3e437fb82ac3924ad15859a3b579`
- final result: `result.json`
- canonical state/event database: `world.sqlite`
- CAS and per-tick observation/cost/load records: `cas/`, `tick-0.json` … `tick-3.json`, `observations.json`, `costs.json`, `loads.json`

The completed result was re-audited from the SQLite replay, event records, CAS references, and evidence hashes: **PASS**.
