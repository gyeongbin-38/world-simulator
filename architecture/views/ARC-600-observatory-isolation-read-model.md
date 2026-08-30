# ARC-600 — Observatory Isolation & Read Model

**Status:** DRAFT / O0  
**Parents:** A00, ARC-240, ARC-270, DF-260  
**Question:** How may the Observatory inspect a run without becoming part of simulation causality or scientific authority?

## Principle

> The Observatory is a read-only instrument over committed experimental facts and explicitly derived presentation data.

The Observatory may fail, disconnect, lag, reorder delivery, or be absent entirely without changing simulation state, cognition, reproduction, visibility, lifecycle, or experimental validity.

This document owns the Observatory authority boundary and read-model contract. It does not own visual styling, sprite trait generation, canonical event semantics, or future researcher intervention controls.

## Authority boundary

The Observatory may read only from sources that are already authoritative or explicitly derived from authoritative sources:

- committed snapshot identity, state version, and state hash;
- committed domain events and transition fragments;
- canonical lifecycle, message, proposal, and lineage state;
- experiment/run metadata required for interpretation;
- immutable ContextPack/raw-generation/evidence/artifact references;
- registered post-hoc analysis results when their derivation identity is available.

The Observatory is never an owner of:

- `ActionIntent` meaning;
- validation law;
- commit order;
- partner selection;
- agent-visible memory/context;
- lifecycle or reproduction eligibility;
- physical coordinates before an explicit causal-space experiment;
- scientific result truth.

## Committed-only semantics

A UI element described as a world fact must resolve to a committed state/event/evidence identity.

Uncommitted model candidates, inference-progress telemetry, transport buffers, renderer guesses, and optimistic UI state cannot be displayed as if they were committed behavior.

Operational telemetry may be shown only when visually and semantically separated from canonical world facts.

## Read-model boundary

The first implementation should expose an immutable projection equivalent to:

```text
ObservatoryFrame
  run_id
  tick
  state_version
  snapshot_hash
  agents[]
  committed_events[]
  lineage_edges[]
  evidence_refs[]
  experiment_identity
  frame_digest
```

Exact field schemas belong to implementation/spec files when O0 implementation begins. The projection is derived from canonical data; it is not canonical state itself.

A projection bug may make the UI wrong. It must not be capable of making the simulation wrong.

## Presentation sidecar

Researcher-facing presentation data belongs outside canonical world state.

Examples:

- display name;
- sprite identity / sprite recipe;
- graph layout coordinates;
- panel open/closed state;
- local selection/focus;
- cached thumbnails;
- animation state;
- zoom/pan state.

Presentation records may be deterministic and persistable for replay ergonomics, but they remain observational metadata.

They must not enter:

- Context Compiler inputs;
- model prompts;
- reproduction law;
- interaction eligibility;
- visibility law;
- resource access;
- lifecycle transitions.

## Display identity

A researcher-facing display identity may map a canonical `AgentId` to:

```text
display_name
sprite_identity
```

The canonical `AgentId` remains the scientific key.

Display names and sprites are hidden from agents in EXP-000. A paper figure or screenshot should preserve a resolvable canonical identifier through inspector metadata, export metadata, or caption provenance.

## Lineage view

Genealogy is derived only from canonical lineage/birth facts.

The Observatory may display:

- parents;
- children;
- ancestors/descendants;
- generation depth;
- birth/death tick;
- founder root;
- exact lineage edges.

It must not infer that lineage implies social knowledge, affinity, inheritance of experience, or behavioral similarity.

## Analysis overlays

Derived metrics are allowed only as overlays with explicit derivation identity.

Examples:

- interaction count;
- degree/centrality;
- descendant count;
- lineage survival depth;
- registered communication motifs.

Researcher labels such as `leader-like`, `coalition-like`, `dominant lineage`, or `attachment-like` are never canonical badges. If shown, they require an analysis definition and must be visually marked as derived interpretation.

## Live source vs replay source

O0 permits two read sources:

1. **Live projection:** an immutable post-commit frame emitted after a canonical tick commit.
2. **Replay projection:** the same logical frame regenerated from durable run/evidence data.

The live projection may be ephemeral. Durable crash/resume validation remains owned by ARC-270/SEQ-250 and is not a prerequisite for the first non-authoritative Observatory shell.

Live and replay should converge on the same projection function as soon as durable replay is available.

## Failure isolation

Observatory failure semantics:

- UI disconnect: simulation continues;
- renderer crash: simulation continues;
- slow client: simulation continues;
- dropped observation frame: scientific run remains valid;
- client reconnect: resume from a committed frame/state version;
- malformed presentation metadata: hide/fallback in UI, never mutate canonical state.

The simulation must never wait for a browser acknowledgement to commit the next tick.

## Future control plane

Researcher-caused interventions are outside O0.

A future UI may request an experiment control action only through the explicit intervention architecture owned by ARC-400/WF-410/SEQ-420 or its successor. A button click must never become a direct state mutation.

## Conformance requirements

Before calling an Observatory adapter supported, tests should prove at minimum:

- headless execution remains valid with no Observatory present;
- UI disconnect cannot alter state hash or event sequence;
- panel/layout/display-name/sprite changes cannot alter ContextPack hashes;
- presentation metadata never appears in agent-visible context;
- only committed behavior is represented as committed;
- canonical lineage edges are preserved exactly;
- a replay projection resolves back to run/tick/state/evidence identities;
- changing visual configuration changes only presentation artifacts, not canonical run results.
