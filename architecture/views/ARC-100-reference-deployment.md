# ARC-100 — Reference Deployment

**Status:** REVIEWED  
**Parent:** ARC-000  
**Question:** Where do computation, active state, evidence, analysis, and visualization live in the first practical local deployment?

## Reference topology

```text
Windows workstation
├─ IDE / launcher
├─ optional desktop Observatory
└─ WSL2 Ubuntu
   ├─ headless simulation process
   ├─ model runtime
   ├─ active durable state
   ├─ artifact/evidence handling
   ├─ tests
   └─ analysis/export
```

Linux/WSL2 is the preferred research runtime. Windows is the host, not a semantic dependency.

## Storage roles

```text
VRAM / RAM
= computation + cache

active durable store
= current authoritative run state / commit metadata

artifact storage
= raw evidence / model outputs / selected contexts / large immutable payloads

cold storage
= models / completed raw runs / checkpoints / exports
```

A Windows drive letter is never part of domain semantics.

Large-capacity D:/external storage may hold cold data. Hot state should use the fastest reliable local storage available.

## Model residency

Where practical:
- one shared immutable base model is loaded once;
- per-agent state remains lightweight;
- later adapters/genomes are references or small deltas, not duplicated full base models.

## Failure classification

Compute/storage/UI failures are infrastructure outcomes. They do not directly become agent death or ecological events.
