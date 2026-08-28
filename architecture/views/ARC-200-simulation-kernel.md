# ARC-200 — Simulation Kernel

**Status:** REVIEWED  
**Parent:** ARC-000  
**Question:** Which responsibilities own one reproducible simulation tick?

## Responsibilities

The conceptual kernel contains these responsibilities:

1. Run Coordinator
2. Tick Coordinator
3. Snapshot Manager
4. Equal Opportunity Scheduler
5. Cognition Gateway
6. Intent Collector
7. Law Validator
8. Communication Protocol
9. Reproduction Protocol
10. Lifecycle Protocol
11. Intervention Protocol
12. Commit Coordinator

Implementation may combine classes/processes, but authority boundaries must remain equivalent.

## Main flow

```text
Run
→ open tick
→ bind immutable S_t
→ enumerate opportunities
→ compile contexts
→ execute cognition
→ close intent batch
→ validate
→ domain planning
→ conflict resolution
→ one commit
→ publish S_(t+1)
```

Exact ordering is owned by SEQ-230.

## Kernel rules

- A model result is not world state.
- Child components cannot independently commit competing versions of the same tick.
- Domain protocols propose transition fragments; the commit boundary owns authoritative mutation.
- Inference may be parallelized, but completion order has no causal priority.
- One baseline cognition opportunity yields at most one primary model-proposed action outcome.
- EXP-000 action vocabulary contains directed communication, bilateral reproduction protocol actions, and WAIT; no movement/resource/trade/combat action exists in the baseline.

## Ownership links

- lifecycle timing → LC-210
- reproduction proposal resolution → LC-220
- state/event/protocol meaning → ARC-240
- causal tick sequence → SEQ-230
