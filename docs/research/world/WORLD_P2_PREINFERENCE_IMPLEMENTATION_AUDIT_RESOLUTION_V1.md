# WORLD P2 Pre-Inference Implementation Audit Resolution V1

Status: IMPLEMENTATION HARDENING / NO P2 MODEL FORWARD OBSERVED

Study: `WORLD_P2_PHASE_DECOUPLED_BEHAVIORAL_ADMISSION_V1`

## Frozen scientific contract remains unchanged

This resolution does **not** modify the frozen P2 preregistration, config,
cohort, thresholds, model-facing interface, generation policy, phase
conditions, or interpretation bounds.

- frozen protocol commit: `299b5ff29a14aef92b977ee53d0cf8e792067f11`
- frozen config SHA-256: `c53bb0d0f037e70df0553cbd17d181b3402cc825812dd8ba1e481f096588e92b`
- pre-hardening implementation parent: `6ba798744437869bc41f013edcc8d97c88b8d733`
- P2 behavioral observations before this hardening: `0`

## Independent pre-inference audit finding

The final pre-inference audit identified one deterministic blocker in the
pre-hardening implementation: P2 branch-order audit runs contain 160 attempts
per order, while the reused A0 branch-order evaluator required exactly 80.
Therefore a P2 run that passed G0/G1/G2 would raise before producing G3/G4.
This was an implementation mismatch, not a scientific observation.

The audit also identified reproducibility/provenance weaknesses that can be
closed without changing the experiment:

1. phase condition was not independently bound to immutable non-model-facing
   execution evidence;
2. constrained argmax tie resolution inherited allowed-token iteration order;
3. a dirty worktree was not explicitly rejected;
4. phase-forward topology was structurally implied but not independently
   asserted against observed forward calls;
5. stdout/archive preservation depended on an unfrozen manual invocation.

## Protocol-neutral hardening

The canonical P2 execution path after this resolution is:

`tools/run_p2_hardened.sh`
→ `tools/world_p2_hardened_entry.py`
→ frozen base runner `tools/world_p2_phase_decoupled_behavioral_admission.py`

The hardened entrypoint installs only the following non-scientific execution
controls:

- P2-specific G3 evaluator requiring the frozen 160-context cohort while
  retaining the exact A0 thresholds (`agreement >= 0.95`, domain-rate spread
  `<= 0.05`, and every order independently satisfying G1-style admission);
- immutable `WORLD_P2_PHASE_EXECUTION_V1` evidence binding condition and
  prefill/selector adapter flags to each raw generation reference without
  altering model-facing bytes or the existing generation ID contract;
- canonical sorted allowed-token order, so exact greedy ties resolve to the
  lowest allowed token ID deterministically;
- fail-closed clean-worktree requirement;
- runtime assertion that exactly one forward without `past_key_values` occurs
  per generation and every later model forward is cache-backed;
- canonical stdout capture and archive verification before any post-hoc work.

## Required pre-inference verification

Before the first P2 model forward:

1. pull the hardening execution commit;
2. run the P2 hardening/unit/contract tests;
3. run only the hardened static `validate` launcher;
4. verify no model was loaded/generated during validation;
5. only then execute the hardened primary launcher.

Any failure after the first model forward must preserve its evidence root and
stdout. Frozen P2 thresholds/configuration must not be changed in response to
observed behavior.

Founder Freeze remains `NOT_ESTABLISHED`.
