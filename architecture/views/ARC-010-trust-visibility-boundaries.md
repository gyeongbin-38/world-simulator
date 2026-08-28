# ARC-010 — Trust & Visibility Boundaries

**Status:** REVIEWED  
**Parent:** ARC-000  
**Question:** Which authority and information boundaries prevent silent contamination of an experiment?

## Core principle

> Information access is part of experimental treatment.

The model receives only an explicitly compiled agent-scoped view. Researcher/analysis/UI information does not leak into that view merely because it exists.

## Authority boundaries

### Researcher → Experiment Controller
Researcher-caused causal changes must enter through explicit experiment-control semantics.

### Experiment Controller → Simulation Kernel
Only validated run/intervention instructions may reach the authoritative transition path.

### Simulation Kernel → Model Runtime
The model receives a bounded ContextPack and returns a proposal. It cannot write state.

### Canonical data → Analysis
Analysis reads immutable/canonical evidence and produces derived artifacts only.

### Simulation → Observatory
Observatory reads projections/events. Rendering state is not simulation state.

## EXP-000 agent-visible categories

The baseline may expose only information explicitly allowed by the experiment condition, including:
- own opaque identity;
- own public self-state such as age;
- active-agent opaque directory;
- directed messages delivered to self;
- pending reproduction proposals addressed to self;
- deterministic bounded history derived from information previously observable by self;
- neutral action mechanics.

## Researcher-only by default

Examples:
- hidden lifespan threshold;
- lineage/parent identity;
- internal random seeds;
- model/checkpoint digest;
- other agents' directed messages;
- analysis labels/community/centrality;
- future private synthetic modulation.

## Cross-run isolation

No private agent history, cache-derived semantic memory, UI annotation, or analysis result from another run may silently become input to the current run.

## Baseline visualization

Sprite appearance/position is researcher-facing and non-causal. If appearance or position later enters an agent ContextPack, that is a new experimental information channel and requires an explicit architecture/experiment change.
