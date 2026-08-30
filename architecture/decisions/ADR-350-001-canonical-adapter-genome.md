# ADR-350-001 — Canonical Adapter Genome Representation

**Status:** ACCEPTED  
**Date:** 2026-08-30  
**Decision owner:** ARC-350

## Context

One immutable base must support many independently inherited neural states.
Runtime quantization and LoRA factor coordinate symmetries cannot define
scientific genotype identity.

## Decision

Use an immutable official BF16/open base checkpoint plus a separate canonical
`AdapterGenome`. The storage genotype is the canonical PEFT/PyTorch LoRA factor
artifact. The effective genotype is the ordered reconstructed delta tensor set
and its digest. Inheritance and mutation operate on effective deltas, followed
by fixed-rank reference factorization into canonical factors.

Generation-0 neural-heredity founders share the base-bound `ZERO_ADAPTER`
sentinel. It has a deterministic canonical and zero-effective digest but no
physical factor artifact until materialization is required. `NullGenome`
continues to mean heredity disabled and is semantically distinct.

GGUF base/LoRA files are derived runtime representations. They record source,
converter, policy, and output identities; they are regenerable and never input
to mutation or crossover. `merge_and_unload()` output is not canonical storage.

## Consequences

- Equivalent factor coordinates may have different storage bytes, but the
  canonical reference factorization selects one admitted child representation.
- Scientific identity is independent of llama.cpp quantization.
- One exact reference construction backend is required; cross-device
  construction bit identity is not claimed.
- CAS stores canonical factor blobs; SQLite stores references and metadata.

The exact codec and rank law are defined by
[`ARC-350`](../views/ARC-350-neural-heredity.md) and exact fields by
[`genome.schema.yaml`](../../specs/domain/genome.schema.yaml).
