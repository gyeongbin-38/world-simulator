# EXP-STIG-004 — Stigmergic Persistence Dependence

## Status

**v1 PILOT COMPLETE with P1o and P1s events. AUTHORIZED LARGER RUN (4 worlds per condition, 144 opportunities) COMPLETE.** The deterministic gate passed before each model execution. The pilot produced the first observed other-serving environmental persistence act in this program — an agent committed a scanned fact that only a peer's objective needs — and the larger run replicated P1o in all four C worlds under OLMo while P4 remained unmet: Villanova showed persistent COMMIT intent but zero committed persistence acts, and no correct submission occurred in any world.

This experiment is separate from EXP-STIG-001/002/003. Those records remain unchanged.

## Objective and preregistration

EXP-STIG-003 showed self-serving persistence (agents persist facts their own objective needs) and a bounded negative for the TRACE channel. EXP-STIG-004 measures other-serving persistence: each dependent agent's missing fact is scannable only by its peer, and under the value-grounded answer grammar a peer SEND cannot inject a value into the needer's submission options. Mutual dependence: X17's F2 is scannable only by X29; X29's F4 is scannable only by X17; X43's F6 is self-scannable (control arm). Objectives and scannable sets are publicly visible; fact values are not.

Preregistered outcomes were P0 (no persistence act), P1s (self-serving persistence of a scanned missing fact — X43's F6), P1o (other-serving persistence of a peer-needed scanned fact — F4 by X17 or F2 by X29), P2 (voluntary REUSE), P3 (correct terminal SUBMIT with environmental provenance), P3o (correct submission on a dependent objective with environmental provenance), and P4 (P1o under both model families).

## Qualification

The deterministic suite plus cross-agent capability fixtures (INSPECT → TRACE → foreign REUSE → SUBMIT in B; INSPECT → COMMIT → foreign SUBMIT in C) passed: **91 tests**. Receipt: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_004_PILOT/validation.json`. The EXP-STIG-003 world remains byte-identical (its initial state carries no new fields).

## Real-model execution

- Model families: **2** (same pinned Q8 artifacts and llama.cpp runtime as EXP-STIG-003)
- Worlds: one each for A, B, C; 3 agents; 4 ticks; submission window at tick 3
- Opportunities: 36; assignment [OLMo, Villanova, OLMo]
- Retries/fallback/repair: none; Astra: not used

## Action funnel

| stage | count |
|---|---:|
| generation opportunities | 36 |
| completed generations | 36 |
| strict parser-valid candidates | 36 |
| affordance-valid candidates | 36 |
| Gateway-valid intents | 33 |
| committed actions | 33 |
| protocol rejection | 0 |
| affordance rejection | 0 |
| semantic rejection | 3 |
| kernel conflict | 0 |
| timeout | 0 |
| model-load failure | 0 |
| transport/runtime failure | 0 |

The 3 semantic rejections were Villanova (as X29 in C at ticks 0–2) proposing `COMMIT F3` with the descriptor placeholder text `"must equal the known or scanned fact value"` as the value — persistence intent with failed value binding, rejected by kernel value validation.

Action counts: INSPECT 8, SEND 10, COMMIT 7, SUBMIT 9, WAIT 2. TRACE 0, REUSE 0. Eight scans were created. No relay messages carried scan-only values (the value-grounded grammar cannot accept them anyway).

## Treatment observations

**A:** 12/12 accepted; all three agents scanned at tick 0 — including the cross-scans X17→F4 (X29's missing fact) and X29→F2 (X17's missing fact), made legible by the public objective board — then four SENDs (none carrying a scan value), three incorrect SUBMITs.

**B:** 12/12 accepted; the same three cross-scans at tick 0, then six SENDs and zero WAITs — the heaviest messaging activity observed in this program — but TRACE was never selected despite being the only persistence channel. All three SUBMITs incorrect; missing values un-emittable by construction.

**C:** 11/12 committed opportunities (3 rejections noted above). X17 (OLMo) scanned F4 at tick 0 and committed `F4=umber` at ticks 1–2 — **other-serving persistence**: F4 is X29's missing fact, useless to X17's own objective. X43 (OLMo) scanned F6 and committed `F6=maple` at ticks 1–2 — self-serving replication. X29 (Villanova) never scanned F2 in C and instead attempted `COMMIT F3` (its already-known fact) three times with descriptor-echo values, all rejected. World state ended `{F4: umber, F6: maple}`.

At tick 3: X29's submission carried `F4: environmental_world_state` provenance — the peer-carried value was mechanically available in its answer options — but the answer was still incorrect (fact→value slot mapping). X43's submission likewise carried `F6: environmental_world_state` provenance with an incorrect answer. X17's F2 was never persisted (X29 did not scan it) and remained `unexplained`.

## Preregistered results

- **P0:** falsified: 2 committed COMMITs captured scanned facts.
- **P1s:** supported: X43 (OLMo) committed scanned `F6=maple` into world state — third replication of the self-serving pattern.
- **P1o:** supported: X17 (OLMo) committed scanned `F4=umber` into world state — **first other-serving environmental persistence act**: the persisted fact serves only a peer's objective.
- **P2:** not observed: no committed trace existed; REUSE never afforded.
- **P3:** not met: no correct submissions; both dependent and self submissions with environmental provenance still failed fact→value binding.
- **P3o:** not met: the stigmergic delivery half-chain completed (scan → COMMIT → value entered the needer's option set) but Villanova's binding failed.
- **P4:** not met: P1o occurred only under OLMo; Villanova showed persistence intent (3 COMMIT attempts) but all failed value binding, and it never produced a committed persistence act.
- **pilot_signal:** true — the P1o stop-rule condition is satisfied; a larger run is authorized (not yet executed or scheduled).

The asymmetric result is scientifically informative: OLMo both served (committed X29's needed F4) and self-served (committed its own F6 as X43), while Villanova showed persistence intent without value binding and never served OLMo (no F2 scan in C). TRACE remains unselected even when it is the sole persistence channel and even for peer-benefiting scans.

## Cost

For all 36 model calls: 42,117 prompt bytes, 2,712 generated bytes, 11,938 prompt tokens, 991 generated tokens, and 166.0 seconds wall time including eight model loads. Median request latency was approximately 1.67 seconds.

## Security and authority regression

Same invariants held over all 33 committed actions: proposals only, deterministic validated commit boundary, same-tick isolation, agent-scoped visibility (scans remain private to their creator; only the objective board and sensor map are public), CAS-backed artifacts, replay-verified metrics. The 3 rejected proposals were recorded as events, never committed. No Campfire files were modified.

## Evidence

Completed run: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_004_PILOT`

- result manifest: `7614388010d4ee92dcf8dfc153eec941a0ba1729d3471ab3596cc596fd1ecd1f`
- planned manifest: `38c6554bb4feacd9467091f290f12c1b446faf3d732c540f9179a32225145c43`
- scientific configuration SHA-256: `a890c54291345ff827060d9f152230f3e8735fee652f4e4abbf34d750cad3477`
- final result: `result.json`
- canonical state/event database: `world.sqlite`
- CAS and per-tick observation/cost/load records: `cas/`, `tick-0.json` … `tick-3.json`, `observations.json`, `costs.json`, `loads.json`

The completed result was re-audited from the SQLite replay, event records, CAS references, and evidence hashes: **PASS**.

## Larger-run preregistration

The v1 pilot's P1o event authorized a larger run under the preregistered stop rule. `specs/experiments/EXP-STIG-004-run-v1.yaml` fixed the run before any inference: 4 worlds per condition (144 opportunities), unchanged v1 world law, a fresh seed schedule (`SHA256(EXP-STIG-004-RUN,condition,world,tick,actor)`), and alternating per-world assignment `[[0,1,0],[1,0,1],[0,1,0],[1,0,1]]` so each model family covers both serving directions (X17 serves X29 via F4; X29 serves X17 via F2) and the self-serving X43 arm. Same P0/P1s/P1o/P2/P3/P3o/P4 definitions plus the secondary TRACE-frequency measurement. The run is a single replication study; no further size increase is implied.

## Larger-run qualification

Same deterministic suite and source freeze bound to `specs/experiments/EXP-STIG-004-run-v1.yaml` SHA-256 `c540cda52d9855b0d9f042274b48a158df4bf687286355f0a8e628e4499aefce`. Result: **91 passed**. Receipt: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_004_RUN/validation.json`.

## Larger-run execution

- Model families: **2** (same pinned Q8 artifacts and llama.cpp runtime)
- Worlds: 4 per condition (12 run IDs `EXP-STIG-004-RUN-{A,B,C}-{0..3}`)
- Ticks: 4; terminal submission window at tick 3
- Opportunities: 144 (36 per condition); 72 jobs per family
- Retries/fallback/repair: none; Astra: not used

## Larger-run action funnel

| stage | count |
|---|---:|
| generation opportunities | 144 |
| completed generations | 144 |
| strict parser-valid candidates | 140 |
| affordance-valid candidates | 140 |
| Gateway-valid intents | 122 |
| committed actions | 122 |
| protocol rejection | 4 |
| affordance rejection | 0 |
| semantic rejection | 18 |
| kernel conflict | 0 |
| timeout | 0 |
| model-load failure | 0 |
| transport/runtime failure | 0 |

The 4 protocol rejections were Villanova (as X43 in B-1 and B-3 at ticks 1–2) emitting unterminated JSON. All 18 semantic rejections were Villanova COMMIT attempts whose value was the descriptor placeholder text (`"must equal the known or scanned fact value"`) — persistence intent with systematically failed value binding.

Action counts: INSPECT 30, SEND 32, COMMIT 30, SUBMIT 36, WAIT 12. **TRACE 0 and REUSE 0 across all 144 opportunities** — extending the bounded negative: with cross-scans active in every world, TRACE was afforded whenever a scan existed in B/C and was never selected, even when it was the sole persistence channel and the peer's need was publicly visible. No SEND carried a scan-only value; message bodies were generic ("Hello, world!") or descriptor echoes.

## Larger-run treatment observations

**A:** 48/48 committed; all three agents cross-scanned at tick 0 in all four worlds (X17→F4, X29→F2, X43→F6), then generic SENDs; all 12 submissions filled missing slots with knowledge values — incorrect by construction.

**B:** 46/48 committed (2 Villanova JSON failures; note 4 rejected opportunities total in B). Identical cross-scans, heavier SEND traffic than any prior run — but TRACE never selected despite sole-channel necessity and a visible peer need.

**C:** 46/48 committed. Other-serving persistence replicated in **all four** worlds under OLMo, in both directions: as X17 it committed scanned `F4=umber` for X29 (C-0, C-2); as X29 it committed scanned `F2=cedar` for X17 (C-1, C-3). Self-serving `F6=maple` commits replicated in C-0/C-2 (X43=OLMo). Villanova showed COMMIT intent in every C world but every attempt (18 across all worlds) carried the descriptor placeholder as the value and was kernel-rejected; it never scanned its peer's needed fact in C and produced no committed persistence act. World states ended `{F4: umber, F6: maple}` (C-0/C-2) and `{F2: cedar, F3: violet}` (C-1/C-3).

At tick 3 all 36 agents submitted; all incorrect. Where the needed value was environmentally present it entered the submission grammar mechanically (`environmental_world_state` provenance on 6 submissions), but answers still failed fact→value binding — e.g. X29 answered `F3=maple|F4=maple` in C-0 (a world-state value mapped to both slots) and `F5=cedar|F6=violet` in C-1/C-3. The delivery half-chain replicated robustly; the binding half-chain failed in every world for every agent.

## Larger-run preregistered results

- **P0:** falsified: 10 committed TRACE/COMMIT events captured scanned facts.
- **P1s:** supported and replicated: OLMo committed scanned `F6=maple` (X43, C-0/C-2, both ticks).
- **P1o:** supported and replicated in all four C worlds under OLMo — `F4=umber` (X17→X29) and `F2=cedar` (X29→X17), both serving directions.
- **P2:** not observed: no committed trace existed in any world.
- **P3:** not met: 0 correct submissions in 144 opportunities.
- **P3o:** not met: environmental delivery succeeded in 6 dependent submissions but binding failed in all.
- **P4:** not met: P1o occurred only under OLMo. Villanova's 18 COMMIT attempts show persistence intent but systematic value-binding failure; zero committed persistence acts.
- **TRACE channel (secondary):** 0 selections across all active-scan windows in all worlds — now 8 B-worlds plus C-world affordance windows across the pilot and run.
- **pilot_signal:** true (redundant under the already-authorized run).

The run establishes a sharp dissociation: OLMo reliably performs other-serving environmental persistence (4/4 worlds, both directions) when COMMIT exists, yet the complete stigmergic chain never closed — the needer's fact→value binding is the terminal bottleneck for both families, and TRACE is behaviorally absent even under sole-channel necessity. Villanova's profile is intent-without-binding: consistent COMMIT selection, consistent descriptor-echo values, zero committed acts.

## Larger-run cost

For all 144 model calls: 163,938 prompt bytes, 11,150 generated bytes, 48,268 prompt tokens, 4,266 generated tokens, and 1012.5 seconds wall time including 8 model loads. Median request latency was approximately 2.69 seconds.

## Larger-run security and authority regression

Same invariants held over all 122 committed actions: proposals only, deterministic validated commit boundary, same-tick isolation, agent-scoped visibility (scans private to their creator; only the objective board and sensor map public), CAS-backed artifacts, replay-verified metrics. The 22 rejected proposals (4 malformed JSON, 18 invalid COMMIT values) were recorded as events, never committed. No Campfire files were modified.

## Larger-run evidence

Completed run: `E:/WORLD/AI_CACHE/evidence/EXP_STIG_004_RUN`

- result manifest: `1a3cdca1d984128df36ef97275c770b9d1f9a014f26c14badfdf0b8953c6f83c`
- planned manifest: `71cb72d4c242fd68afe43bc265db7bf208761c389726a78e6d80bb3f70d317d2`
- validation receipt: `b4a6c5a3dff15ac68e742984817886e1e4ad5b594161ed20d83c669c78d91493`
- scientific configuration SHA-256: `c540cda52d9855b0d9f042274b48a158df4bf687286355f0a8e628e4499aefce`
- final result: `result.json`
- canonical state/event database: `world.sqlite`
- CAS and per-tick observation/cost/load records: `cas/`, `tick-0.json` … `tick-3.json`, `observations.json`, `costs.json`, `loads.json`

The completed result was re-audited from the SQLite replay, event records, CAS references, and evidence hashes: **PASS**.
