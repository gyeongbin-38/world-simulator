# EXP-STIG-006 — REUSE-Necessary Stigmergic Read Path

## Status

EXECUTED — pilot (36 opportunities) and authorized larger run (108
opportunities, 3 worlds/condition, Latin-square `[[0,1,2],[1,2,0],[2,0,1]]`)
both complete with audit PASS. Findings are recorded in
`docs/research/world/EXP-STIG-006-results.md`.

This experiment extends EXP-STIG-005. The EXP-STIG-003/004/005 lineages
remain authoritative for their own evidence.

## Motivation

EXP-STIG-005 produced the first TRACE-channel completion — and exposed a
structural flaw in the measurement surface: committed trace values enter
the submission-window grammar directly, so REUSE (internalizing a trace
into persistent knowledge) offers nothing the window does not already
provide. P2 (voluntary REUSE) is therefore not merely unobserved; it is
unmeasurable under the EXP-STIG-003–005 window law — the stigmergic read
path bypasses internalization entirely.

EXP-STIG-006 closes that gap with one law change: trace values no longer
enter window answer options directly. A trace's value reaches the window
grammar only through persistent knowledge — i.e., only after REUSE. World
state values (C) still enter directly, so the B condition becomes the sole
measurement of the trace read path: scan → TRACE → REUSE → SUBMIT. The
question is whether any family internalizes a committed mark — including
SmolLM3, which binds values but has never scanned.

## World

Identical to EXP-STIG-004/005 in every law-level detail except the trace
read law: same agents, facts, objectives, initial knowledge, scannable
sets, mutual dependence, public objective board and sensor map, scan
expiry, terminal submission window at tick 3, and the value-grounded
answer grammar.

### Agent-visible information change

Relative to EXP-STIG-004/005, the submission-window value set excludes raw
trace values. Window options are drawn from persistent knowledge union, in
C, committed world_state values. A committed trace's value enters options
only after an agent internalizes it via REUSE (which places the fact into
the actor's knowledge). Traces remain visible data — id, creator, fact_id,
value, note — so the value is seen but is not emittable until
internalized. The interface line "trace values must be internalized by
REUSE before they can appear in an answer" is disclosed under this
document's authority for agent-visible changes; EXP-STIG-004/005 worlds
and evidence are unchanged.

## Model cohort

Same three pinned families as EXP-STIG-005 (OLMo index 0, Villanova index
1, SmolLM3 index 2). Pilot assignment [[2, 0, 1]]: X17=SmolLM3 needs F2
and can receive it only via REUSE of X29's trace (B) or X29's COMMIT (C);
X29=OLMo serves; X43=Villanova carries the self-serving arm.

## Preregistered outcomes

- P0 — no committed TRACE or COMMIT captures any scanned fact.
- P1s — a committed TRACE or COMMIT captures X43's scanned missing fact.
- P1o — a committed TRACE or COMMIT captures a scanned fact needed by a
  peer.
- P2 — at least one voluntary REUSE of a committed trace, self or foreign.
  Under the new window law this is the primary measurement: whether the
  stigmergic read path is used at all.
- P3 — at least one correct terminal SUBMIT whose missing objective facts
  all carry environmental provenance.
- P3o — a correct submission on a dependent objective with environmental
  provenance; in B, completing it requires a foreign REUSE — the full
  stigmergic write-read chain.
- P4 — P1o occurs under at least two distinct model families.

## Stop rule

The pilot is bounded at 36 opportunities. A larger run is authorized only
if at least one P2 or P1o event occurs, any P3/P3o event occurs, or
another scientifically justified signal is recorded in the sealed result
receipt.

## Execution gate and durability

Same gate: deterministic suite, affordance qualification, and the
cross-agent capability fixture — which under this law exercises the full
INSPECT → TRACE → foreign REUSE → SUBMIT path in B. The runner refuses
stale validation, hash-mismatched artifacts, or an already-started
evidence root.

## Frozen design before any model forward

specs/experiments/EXP-STIG-006-v1.yaml owns exact sizes, seeds, values,
cohort, and assignment; its execution overlay
specs/experiments/EXP-STIG-006-execution-pilot.yaml is digest-bound to it.

Greedy deterministic completion, same mechanical renderer, no system
instruction, chat template, history replay or Astra. No retries, repair or
fallback. All model files, code/spec hashes and runtime executable hashes
bind a pre-execution manifest before generation. No threshold, model
setting, horizon or label changes after observing results.
