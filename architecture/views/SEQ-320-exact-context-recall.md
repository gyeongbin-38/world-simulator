# SEQ-320 — Exact Context Recall

**Status:** REVIEWED  
**Parent:** ARC-300  
**Freeze state:** IMPLEMENTATION-READY  
**Question:** Can an EXP-000 agent expand its bounded ContextPack by requesting exact prior context?

## EXP-000 decision

> EXP-000 has no agent-triggered recall tool.

The baseline uses the mandatory current categories plus the deterministic
bounded personal-visible history selected by DF-310. `ContextPolicy.recall_mode`
is `DISABLED`, the action presentation contains no recall affordance, and an
ActionIntent cannot request retrieval.

This is the simplest scientifically defensible baseline: it avoids introducing
a second policy-controlled cognition loop, retrieval-query skill, semantic
search bias, variable tool-call opportunity, or hidden memory channel before
those effects are intentional experimental treatments.

## Baseline sequence

```text
bind S_t and cognition opportunity
        ↓
compile mandatory current information
        ↓
select exact bounded personal-visible history
        ↓
finalize and hash ContextPack
        ↓
one model execution
        ↓
ActionIntent
```

There is no recall request/response phase between compilation and model
execution and no model-controlled second pass. Missing history beyond the
frozen bound remains unavailable for that opportunity.

## Deferred exact-reference treatment

A later experiment may introduce deterministic exact reference expansion only
through a new reviewed policy/version. If introduced, it must:

- search only source records already visible to that same agent under ARC-300;
- remain bound to the same immutable `S_t` and opportunity;
- return exact source slices with complete provenance, never a lossy semantic
  summary;
- exclude peer-private data, global hidden history, lineage, researcher
  annotations, analysis labels, and same-tick outputs;
- define deterministic query grammar, result ordering, limits, failure
  behavior, and context identity effects;
- preserve exact ContextPack/request/response artifacts for research lineage;
- add no embedding-first or vector-database requirement.

Whether such expansion consumes the single cognition opportunity, permits a
second model call, or becomes a protocol action is deliberately unresolved and
must be owned by that future treatment architecture. Implementations cannot
preempt it through an undocumented helper.

## Restart and replay

Because baseline recall is disabled, restart reproduces the same bounded pack
from the same `S_t`, source evidence, and policy. Recovery cannot expand the
history window, substitute a semantic cache, or call a model to reconstruct
memory. Replay reads the recorded ContextPack artifact and never invokes recall
or model inference.

## Required conformance

The DF-310 acceptance suite is the single owner of ContextCompiler test names.
Its baseline tests must demonstrate that no model-written semantic memory or
hidden source enters context, policy changes alter identity, and restart/reload
reproduces the exact hash. A future recall treatment requires a separate test
set before activation.

## Owner boundaries

- ARC-300 owns what is visible and hidden.
- DF-310 owns baseline history selection, provenance, ordering, and hashing.
- SEQ-230 owns one same-snapshot cognition opportunity and tick barriers.
- ARC-270/SEQ-250 own durable artifact and restart semantics.
- This view owns only recall availability and the recall/compilation sequence.

