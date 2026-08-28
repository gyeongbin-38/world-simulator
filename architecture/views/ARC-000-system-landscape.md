# ARC-000 — System Landscape

**Status:** REVIEWED  
**Parent:** A00  
**Question:** What belongs to A-LifeLM at the highest useful runtime level?

## Main path

```text
Researcher
  ↓
Experiment Controller
  ↓
Simulation Kernel
  ├─ Context Compiler → Model Runtime → ActionIntent
  ├─ Communication
  ├─ Reproduction
  ├─ Lifecycle
  └─ Intervention boundary
  ↓
Validation + Commit
  ├─ Canonical State
  ├─ Immutable Events
  └─ Raw Evidence Artifacts
       ├─ Analysis
       └─ Observatory
```

## Ownership

- Researcher: defines/observes experiments.
- Experiment Controller: validates run configuration and explicit interventions.
- Simulation Kernel: owns causal tick coordination.
- Context Compiler: selects the allowed bounded view for one agent.
- Model Runtime: performs inference only.
- Domain protocols: construct deterministic transition candidates.
- Commit boundary: owns canonical mutation.
- Analysis: derives research results without world-write authority.
- Observatory: visualizes and submits researcher requests through controlled experiment interfaces.

## Forbidden direct authority paths

```text
Model Runtime  -X-> Canonical State
Observatory    -X-> Canonical State
Analysis       -X-> Canonical State
External repo  -X-> Domain ownership
```

External libraries/frameworks are replaceable implementation components, never the source of A-LifeLM semantics.

## Expansion

- authority/information isolation → ARC-010
- deployment → ARC-100
- kernel internals → ARC-200
- research evidence → DF-260
