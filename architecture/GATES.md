# Architecture Gates

## F0 — Foundation

**Status: CLOSED / REVIEWED**

Owns:
- system authority;
- trust/visibility boundaries;
- reference deployment roles;
- kernel ownership;
- state/event/protocol separation;
- lifecycle;
- reproduction proposal lifecycle;
- one-tick causal ordering;
- research lineage.

`VALIDATED` requires executable implementation evidence; document review alone is not validation.

## D0 — Durable Run & Replay

Author immediately before durable persistence/replay.

Minimum future documents:
- ARC-270 Durable Commit & Replay Boundary
- SEQ-250 Crash Recovery & Resume

Exit intent:
- no partial authoritative commit;
- restart/replay preserves committed history;
- raw evidence remains addressable.

## X0 — Experimental Validity

Author before production confirmatory experiment workflows.

Exit intent:
- discovery/confirmation cohorts are distinguishable;
- intervention schedules and primary analyses can be frozen;
- censoring/exclusions are explicit.

## R0 — Compute & Storage Control

Author before aggressive scaling/batching/model swapping.

Exit intent:
- compute optimizations cannot alter simulation causality;
- resource pressure is measured rather than hidden.

## O0 — Observatory

**Status: ARCHITECTURE DRAFT / IMPLEMENTATION NOT YET ADMITTED**

Owners:
- ARC-600 Observatory Isolation & Read Model;
- SEQ-610 Live / Replay Observation Sequence;
- ARC-620 Observatory Research Views;
- `docs/observatory/SPRITES.md` for presentation-only sprite identity;
- `docs/observatory/DESIGN_SYSTEM.md` for UI visual language.

Exit intent:
- UI can fail/disconnect without changing simulation;
- only committed facts are represented as committed;
- rendering/layout/display identity remains non-causal unless an explicit physical experiment says otherwise;
- display names and sprite traits remain hidden from agents in EXP-000;
- genealogy resolves exactly to canonical lineage facts;
- headless experiment execution remains authoritative with no Observatory present.

Implementation admission requires conformance tests for isolation, deterministic projection identity, display-name/sprite non-leakage, committed-only rendering, lineage fidelity, and headless equivalence.

## Founder admission and post-freeze branches

Founder model admission is sequential:

```text
C0 -> C20 -> Motor -> Autonomous -> Founder Freeze
```

After Founder Freeze, work branches without a dependency between M2 and N0:

```text
Branch A
  resolve remaining baseline architecture blockers, including SELF_SEND
  -> M2 using EXP-000 NullGenome
  -> headless EXP-000 baseline validation

Branch B
  N0 heredity operator/backend admission
```

N0 is not a prerequisite for M2. A neural-heredity experiment requires both a
validated headless EXP-000 baseline and an admitted N0 operator/backend.

## N0 — Neural Heredity

**Status: ARCHITECTURE CLOSED / IMPLEMENTATION-READY**

ARC-350 and SEQ-351 freeze the model-independent neural-heredity foundation.
The bounded operator admission remains future work and does not enable heredity
in EXP-000 or block M2.

Exit result:
- genetic and cultural inheritance are separate;
- parent transcript/private history and observer metrics are excluded;
- C0 compatibility, symmetric operators, mutation, RNG, CAS/commit, PEFT, and
  GGUF derivation boundaries are versioned;
- H1 and H2 admission is validity/viability based and cannot become performance
  selection.
