# EXP-STIG-INTEGRATION — Stigmergic Persistence Track (001–006)

## Status

INTEGRATION RECORD. This document consolidates the supported claims of the
EXP-STIG-001–006 line into a single reference. It asserts no new evidence:
every claim below is backed by the sealed, audit-passed per-experiment
records cited in the evidence table. Each experiment's own owner and
results documents remain authoritative for their detail; where this
document summarizes, the cited record governs.

## Track question

Can artificial agents in this platform use the environment as a persistent
communication medium — writing information that outlives an interaction
and that another agent (or the same agent later) can read to satisfy an
objective — under deterministic causality, proposal-only model output, and
mechanically audited provenance?

## Experiment arc

| exp | design change | opportunities (pilot + run) | key result |
|---|---|---|---|
| 001 | baseline A/B/C: message / persistent trace / causal world | R2 108 (censored), R3 108, R4 108 | interface generations: codec-censored → constrained codec → grounded affordance; no trace bootstrap |
| 002 | instrumental necessity: expiring scans + scored SUBMIT | 18 | bounded negative bootstrap; COMMIT used for known facts; no TRACE/REUSE/SUBMIT |
| 003 | persistence-necessary: persistence is the only self-sufficient route to a correct answer | 36×3 (v1–v3) + 144 | P1 (self-serving COMMIT) and P3 (correct submission, environmental provenance) under OLMo; v3 value-grounded grammar made provenance-correct answers constructible |
| 004 | mutual dependence: needer's fact scannable only by peer; public objectives | 36 + 144 | P1o other-serving persistence replicated 4/4 C-worlds both directions (OLMo); 0 correct — needer binding is terminal bottleneck; TRACE 0 |
| 005 | three-family cohort adds SmolLM3 | 36 + 108 | first complete dependent chain (P3o); replicated in run; first TRACE completion (B-1); capability split emerges |
| 006 | REUSE-necessary read law: trace values reach window only via REUSE | 36 + 108 | P1s/P1o/P3/P3o replicated; TRACE selected once (rejected, descriptor value); REUSE never selected — bottleneck is trace writing, upstream of REUSE |

All runs used greedy deterministic decoding (temperature 0, top_k 1), no
retries/repair/fallback/Astra, no system instruction or chat template, and
fresh preregistered seed schedules. Every run below passed its sealed audit.

## Consolidated supported claims

**C1 — Interface generation, not capability alone, gates measurement.**
Four instrument generations each removed a distinct failure class: R2's
strict codec was output-censored (no scientific estimate); R3's constrained
codec produced semantically impossible references (72/72 REUSE rejected);
R4's grounded affordance eliminated impossible references (102 committed
actions) but could not create necessity; the value-grounded SUBMIT grammar
(003 v3) made unpersisted values un-emittable, collapsing provenance and
correctness into one mechanical check. Each generation converted an
unmeasurable question into a measurable one.

**C2 — Voluntary environmental persistence is real and replicable — under
one family.** OLMo committed scanned objective facts to canonical world
state voluntarily: self-serving in EXP-STIG-003/004/005/006 and
other-serving in EXP-STIG-004/005/006, in both service directions, under
alternating and Latin-square assignments. This is the line's central
positive result: a model writes information to the environment that it
does not itself need, benefiting a peer whose need is publicly visible.

**C3 — Complete stigmergic chains close by division of labor, not
single-model omnipotence.** Three dependent completions exist (EXP-STIG-005
pilot, EXP-STIG-005 run, EXP-STIG-006 run), all with the same structure:
OLMo scans and commits the peer-needed fact; SmolLM3 binds the
environmental value into the correct answer slot with
`environmental_world_state` provenance. No single model in this cohort has
completed serve-and-bind alone in a dependent role.

**C4 — The capability profile is three-way and stable across rotations.**
- **OLMo — server:** scans (9+ per run), persists (all committed
  persistence acts in 004/005/006), completed one TRACE write (005),
  attempted another (006). Unreliable binder.
- **SmolLM3 — binder:** never scanned, never persisted; binds correctly
  when a value is served (P3o completions).
- **Villanova — intent-without-binding:** selects persistence actions
  (COMMIT, TRACE) but emits descriptor-echo values (18 rejections in 004;
  more in 005/006) and malformed JSON; zero committed persistence acts.

**C5 — The TRACE/REUSE channel is behaviorally near-absent, and the
bottleneck is the write.** Across the full track (~750+ measured
opportunities in B/C worlds where TRACE was afforded), TRACE was selected
twice: one committed trace (EXP-STIG-005 B-1, completing a self-serving
`environmental_trace` chain — the channel is usable when chosen) and one
rejected attempt (EXP-STIG-006 B-1, descriptor-echo value). REUSE was never
selected anywhere, including under EXP-STIG-006's law where internalization
was the *only* route for a trace value to reach an answer. The read side
of stigmergy remains unmeasured not because it was shown absent, but
because the write side almost never activates — and when selected, can
fail at the same fact→value binding step that gates submissions.

**C6 — P4 (cross-family persistence) was never met.** In every run, all
committed persistence acts belong to OLMo. Environmental persistence in
this cohort is single-family; whether it is a general capability or an
OLMo-specific behavior is unresolved by design.

**C7 — Binding is the dominant residual bottleneck.** Correct submissions
required fact→value slot binding after a value was visible; failures took
three forms: template/descriptor echoes (early grammar generations),
real-value-wrong-slot mappings (later), and descriptor values inside
write actions (Villanova). The value-grounded grammar removed the first
class by construction; the other two persisted through 006.

## Negative results are bounded

Zero counts above are bounded to: this three-family local cohort
(OLMo-1B / Villanova-2B / SmolLM3-3B GGUF), 2–4 tick horizons, the specific
grounded affordance grammars used, and opportunity counts of 18–144 per
condition. They are evidence about behavior under these conditions, not
evidence that persistent traces lack value or that larger/other models
would not select them.

## Unmeasured or open questions

1. **Foreign REUSE:** only one committed trace exists in program history
   and it was never reused; whether any family internalizes a peer's mark
   remains untested behaviorally.
2. **Trace-write binding:** EXP-STIG-006 shows the write path fails at
   value binding even when selected. An instrument isolating write-side
   binding (e.g., grounded value options inside TRACE, mirroring the
   SUBMIT fix) would separate selection reluctance from binding inability.
3. **P4 closure:** a fourth family, or a larger member of an existing
   family, is needed to test whether persistence generalizes beyond OLMo.
4. **Scale:** multi-needer amplification of a single mark, longer
   horizons, and larger fact sets are unmeasured (ecological validity).
5. **Relay channel:** SEND traffic was universally generic across all
   runs; whether directed content can substitute for environmental
   persistence is unmeasured (the v3 grammar intentionally makes it
   impossible for correctness, so this needs a different instrument).

## Evidence index

| run | root | result manifest |
|---|---|---|
| 001 R2 (censored) | `EXP_STIG_001_R2` | `ebb1b7d4b40fd25b5bdc7e8647e3b607be0ce5564ae21a69ab276feffbd1fa8e` |
| 001 R3 | `EXP_STIG_001_R3_RUN2` | `2e51e173c99a7bfa0acd9760f8f5da2ee2f323f9a08fb91073e769fc2a7b09c9` |
| 001 R4 | `EXP_STIG_001_R4` (run) | `409409e8006b68d263b4a67f5678fe6bb537796a5f0d2565c9725320fb53c944` |
| 002 pilot | `EXP_STIG_002_PILOT_RUN4` | `8732d3419be3746d0c57e79a3866fd1477de2bce57261a7c6fe38ae962849708` |
| 003 v3 run | `EXP_STIG_003_RUN_V3` | `ad1f720dc38769014e5b9234a084e3d248854258cae176568fe44643215eb746` |
| 004 run | `EXP_STIG_004_RUN` | `1a3cdca1d984128df36ef97275c770b9d1f9a014f26c14badfdf0b8953c6f83c` |
| 005 pilot | `EXP_STIG_005_PILOT` | `2255ddb5f05d7ddee79b9a11e542ed9b43af94f604f580ca51d9819bcef55410` |
| 005 run | `EXP_STIG_005_RUN` | `ea16d9e424e03482118f29c59b71d773a215f54fd1d83a267f48bcc33fd695d1` |
| 006 pilot | `EXP_STIG_006_PILOT` | `ef82402cfab197940f292f10846605352eeb38d226c61414fb7d934709711d93` |
| 006 run | `EXP_STIG_006_RUN` | `6e0cbb64fddc0648538d91781085313ed90d1cc6127a0940805ec01c858db196` |

All evidence roots are under `E:/WORLD/AI_CACHE/evidence/` and are
immutable CAS-backed records; each was re-audited from SQLite replay,
event records, CAS references, and evidence hashes with result PASS.

## Track closure note

The stigmergic-persistence track answered its motivating question
affirmatively in a specific form: environmental persistence emerges
voluntarily under necessity, serves peers when their needs are visible,
and completes dependent objective chains — through division of labor
between capability profiles rather than any single omnipotent agent. The
channel specifically designed for stigmergy (TRACE/REUSE) remains nearly
unused; agents prefer canonical world-state writes when available. Further
claims require new preregistered instruments, per the platform's
confirmatory-evidence rule.
