# ADR-350-002 — Same-Base Symmetric Neural Inheritance

**Status:** ACCEPTED  
**Date:** 2026-08-30  
**Decision owner:** ARC-350

## Context

Autonomous proposal/acceptance is social protocol metadata, not a biological
dominance rule. Direct neural crossover is interpretable only when tensor
identity is exact.

## Decision

N0 admits direct inheritance only for `C0_EXACT_BASE`. Other base digests,
compatible-topology checkpoints, partial target-module matches, and
cross-architecture parents fail closed.

H1 uses an exact 0.5/0.5 effective-delta blend. H2 uses one deterministic
50/50 selection bit per canonical target module. Both are symmetric laws.
Parents are sorted by stable genome identity before contribution or RNG use, so
proposer/acceptor roles and API argument order cannot bias contribution.

H1 and H2 are separate treatments. Passing admission retains both; benchmark,
intelligence, phenotype, social, or reproduction outcomes cannot select a
winner. M1 mutation parameters are manifest-pinned and never tuned from
descendant performance.

## Consequences

- `inherit(A, B, seed)` equals `inherit(B, A, seed)` at the realized effective
  genotype for H1/H2.
- N0 does not implement cross-checkpoint or cross-architecture reproduction.
- Admission measures validity, determinism, integrity, loadability, and minimum
  viability only.

Semantic law is defined by
[`ARC-350`](../views/ARC-350-neural-heredity.md); executable admission cases are
defined by
[`N0-heredity-operator-admission.yaml`](../../specs/experiments/N0-heredity-operator-admission.yaml).
