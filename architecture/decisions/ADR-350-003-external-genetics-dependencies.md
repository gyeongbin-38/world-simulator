# ADR-350-003 — External Genetics Dependencies

**Status:** ACCEPTED  
**Date:** 2026-08-30  
**Decision owner:** ARC-350

## Decisions

| Dependency | Role | Decision | Boundary |
|---|---|---|---|
| Hugging Face PEFT | Primary runtime adapter backend | `ADOPT` | Implement `PEFTAdapterBackend`; do not expose PEFT classes in domain contracts or canonize merged base weights |
| `ZhangYiqun018/GENOME` | Heredity implementation reference | `ADAPT_PRIMITIVES_ONLY` | Tensor crossover, Gaussian/mask mutation, LoRA population representation, and TIES/DARE validation may inform isolated implementations |
| mergekit | Future/offline `WeightGenome` laboratory | `OPTIONAL` | May validate merges/LoRA extraction; never core runtime authority, benchmark evolution, or canonical persistence |
| AgentSociety2 | Replay/schema/analysis design reference | `ADAPT_DESIGN_ONLY` | Dataset catalog, semantic column metadata, DuckDB/export, and trace concepts only; never replace SQLite/CAS or import agent reasoning/social priors |
| LLM-Ecosystem-Andrii-Shramko | Conceptual neighbor / related-work candidate | `REFERENCE_ONLY` | No implementation dependency |

## Rejections

GENOME is not used as an evolution engine. Elite preservation, benchmark
fitness, tournament/roulette/rank selection, fitness-weighted reproduction,
benchmark-driven succession, completion-order causality, and global
Python/NumPy/Torch RNG are rejected.

`mergekit-evolve`, CMA-ES benchmark fitness, and benchmark-driven model
selection are rejected. AgentSociety2 `PersonAgent`, predefined profiles,
ReAct, PlanExecute, TODO systems, personality/social memory, and reasoning
priors are rejected.

## Scientific distinction

A-LifeLM's first neural-heredity study uses one founder checkpoint, minimal
initial ecology, no central fitness, autonomous bilateral mate selection, and
observer-only evaluation. External tools implement or inform bounded adapters;
they do not own these causal laws.

The dependency decisions preserve A00 model independence and the semantic
boundary defined by [`ARC-350`](../views/ARC-350-neural-heredity.md).
