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

Author before authoritative Observatory implementation.

Exit intent:
- UI can fail/disconnect without changing simulation;
- rendering/layout remains non-causal unless an explicit physical experiment says otherwise.

## N0 — Neural Heredity

Author only before parameter/adaptor inheritance.

Exit intent:
- genetic and cultural inheritance are separable;
- no parent transcript leakage;
- crossover/mutation are versioned treatments.
