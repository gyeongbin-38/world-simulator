# EXP-STIG-005 — Cross-Family Stigmergic Persistence Cohort

## Status

PILOT COMPLETE — P1o, P3, and P3o recorded (first completed cross-agent
stigmergic chain: OLMo persisted F2 for X17; SmolLM3 bound and submitted
correctly). Audit PASS; sealed results live in
docs/research/world/EXP-STIG-005-results.md. A Latin-square larger run is
authorized by the stop rule but not yet executed.

This experiment extends EXP-STIG-004. The EXP-STIG-003 lineage (v1 bounded
negative, v2 first P1, v3 first P3, authorized 144-opportunity run) and the
EXP-STIG-004 lineage (first other-serving persistence, replicated 4/4 under
OLMo) remain authoritative for their own evidence.

## Motivation

EXP-STIG-004 established a sharp dissociation: OLMo voluntarily persists a
scanned fact that only a peer's objective needs — replicated in all four C
worlds in both serving directions — yet the complete stigmergic chain never
closed because the needing agent's fact-to-value binding failed in every
world for both cohort families. Villanova showed a consistent
intent-without-binding profile: COMMIT selection with descriptor-echo
values, all kernel-rejected, zero committed persistence acts.

Two questions remain open and are jointly measured here:

1. Does the dissociation replicate under a third model family, or is it an
   artifact of the 1-2B Q8 cohort?
2. Can any locally runnable family close the complete dependent chain
   (scan → persist → environmentally-provenanced correct dependent
   submission)?

## World

Identical to EXP-STIG-004 in every law-level detail: same agents, facts,
objectives, initial knowledge, scannable sets, mutual dependence structure,
public objective board and sensor map, scan expiry, terminal submission
window at tick 3, and the value-grounded answer grammar. The world
implementation is reused unchanged through the `EXP-STIG-005` registry
entry in `src/alifelm/experiments/retention_world.py`; only the experiment
identity differs.

- X17: objective F1=v|F2=v; knows F1; scannable {F4} — serves X29.
- X29: objective F3=v|F4=v; knows F3; scannable {F2} — serves X17.
- X43: objective F5=v|F6=v; knows F5; scannable {F6} — self-serving arm.

## Model cohort

Three pinned local families, one per index; per-world assignment is a
heterogeneous permutation:

- index 0: OLMo-2-0425-1B-Instruct Q8_0 (cohort carryover)
- index 1: Villanova-2B-2603 Q8_0 (cohort carryover)
- index 2: SmolLM3-3B Q4_K_M (new family; quantization and parameter scale
  differ from the Q8 1-2B cohort — this capacity/quantization confound is
  disclosed in the scientific spec rather than controlled)

Pilot assignment `[[2, 0, 1]]`: X17=SmolLM3 serves F4→X29 and needs F2;
X29=OLMo serves F2→X17 and needs F4 (reverse-direction other-serving
replication); X43=Villanova occupies the self-serving arm — the simplest
persistence task for the family with zero committed persistence acts.

## Preregistered outcomes

- P0 — no committed TRACE or COMMIT captures any scanned fact.
- P1s — a committed TRACE or COMMIT captures X43's scanned missing fact
  (first self-serving opportunity for Villanova).
- P1o — a committed TRACE or COMMIT captures a scanned fact needed by a
  peer (primary stigmergic measurement).
- P2 — at least one voluntary REUSE of a committed trace, self or foreign.
- P3 — at least one correct terminal SUBMIT whose missing objective facts
  all carry environmental provenance.
- P3o — a correct submission on a dependent objective with environmental
  provenance: a completed cross-agent stigmergic chain.
- P4 — P1o occurs under at least two distinct model families.

## Stop rule

The pilot is bounded at 36 opportunities (one world per condition, three
agents, four ticks). A larger run is authorized only if at least one P1o
event occurs, any P3/P3o event occurs, or another scientifically justified
signal is recorded in the sealed result receipt. An authorized larger run
uses a Latin-square assignment covering each family in each role once per
condition.

## Authorized larger run (version 1.0.0-run)

The v1 pilot sealed P1o and P3o events, so the stop rule admits a larger
run. specs/experiments/EXP-STIG-005-run-v1.yaml fixes that run's size and
assignment before execution; world law is unchanged from v1. The run
executes 3 worlds per condition (108 opportunities) with a Latin-square
assignment [[0,1,2],[1,2,0],[2,0,1]] covering each family in each role
once per condition, a fresh seed schedule disjoint from the pilot, and the
same outcome definitions plus the secondary TRACE-frequency measurement.
The run is a single replication study, not an iterated search; no further
size increase is implied.

## Execution gate and durability

Same gate as EXP-STIG-004: the deterministic suite, affordance
qualification, and the cross-agent capability fixture must pass before real
inference; the runner refuses stale validation, hash-mismatched artifacts,
or an already-started evidence root. The runner's model-cohort count and
assignment validation are generalized to N families without changing world
law; EXP-STIG-003/004 sealed evidence is unaffected.

## Frozen design before any model forward

specs/experiments/EXP-STIG-005-v1.yaml owns exact sizes, seeds, values,
cohort, and assignment; its execution overlay
specs/experiments/EXP-STIG-005-execution-pilot.yaml is digest-bound to it.

Greedy deterministic completion (temperature 0, top_k 1, top_p 1, min_p 0,
repeat penalty 1, n_predict 128) uses the same mechanical renderer for all
three models with no system instruction, chat template, history replay or
Astra. The grounded affordance grammar narrows proposals to currently
executable actions and visible references; Gateway/kernel validation
remains authoritative. No retries, repair or fallback. All model files,
code/spec hashes and runtime executable hashes bind a pre-execution
manifest before generation. No threshold, model setting, horizon or label
changes after observing results.
