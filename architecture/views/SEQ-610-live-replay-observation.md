# SEQ-610 — Live / Replay Observation Sequence

**Status:** DRAFT / O0  
**Parent:** ARC-600  
**Question:** How does committed simulation data reach the Observatory in live and replay modes without changing causality?

## Live sequence

```text
Simulation tick executes
  -> canonical validation/commit completes
  -> committed snapshot/state_version/state_hash exist
  -> Observatory projector derives immutable frame
  -> optional presentation sidecar enrichment
  -> transport publishes frame
  -> client deduplicates/orders by committed identity
  -> UI renders
```

The projector runs after commit. A client acknowledgement is never part of the simulation commit barrier.

## Frame identity

A live/replay frame must carry enough identity to detect duplicates and stale delivery. The intended key material is:

```text
run_id
tick
state_version
snapshot_hash
projection_schema_version
frame_digest
```

Transport sequence numbers may exist for operations, but they are not scientific causal identity.

## Projection rules

The projector may include only committed facts plus clearly marked derived presentation/analysis fields.

A frame may contain:

- active/dead agent records;
- canonical agent IDs;
- committed message/proposal/birth/death facts;
- canonical lineage edges;
- artifact/evidence references;
- experiment/model/treatment identity needed for inspection;
- presentation-only display names and sprite references;
- registered analysis overlays with derivation identity.

Raw model text should normally remain reference-addressed and fetched on demand rather than pushed into every frame.

## Live delivery

Live transport is non-authoritative.

Allowed operational behavior:

- coalesce superseded UI frames for a slow client;
- drop presentation frames under backpressure;
- reconnect and resume at a later committed frame;
- maintain multiple independent clients.

Forbidden behavior:

- block canonical commit waiting for a UI client;
- make wall-clock delivery order decide simulated order;
- turn dropped UI frames into dropped canonical events;
- retry model cognition because the UI missed an update.

If the live client misses ticks, the UI must indicate that the live visualization skipped frames rather than inventing intermediate world states.

## Client ordering and deduplication

Clients accept only frames whose committed identity is internally consistent.

For a single run:

- lower `state_version` than the currently rendered committed frame is stale;
- identical frame identity/digest is a duplicate;
- same committed identity with a different digest is an integrity error;
- a forward gap is allowed for live display but must be surfaced as a skipped-observation interval.

Client-side animation timing never changes event order.

## Detail inspection

Selecting an agent/event may trigger exact-reference expansion:

```text
frame evidence_ref
  -> artifact/evidence read
  -> ContextPack / raw generation / parse result / validation trace
  -> inspector
```

This is a researcher read path only. It must not feed the retrieved content back into model context or simulation memory.

## Replay sequence

When durable replay is available:

```text
run identity selected
  -> durable committed history loaded
  -> target tick/state version resolved
  -> same Observatory projection logic applied
  -> presentation sidecar deterministically reconstructed/loaded
  -> UI renders
```

Replay controls such as play, pause, step, seek, and speed affect only presentation time.

Replay is not fresh inference and must never be labeled replication.

## Live-to-replay handoff

A completed live run should be inspectable through replay without changing semantic identifiers.

The long-term target is:

```text
same committed run facts
+ same projection schema/config
= same logical ObservatoryFrame
```

Presentation animation state and local panel state are excluded from this equivalence.

## Observatory disconnect

The expected failure sequence is:

```text
client disconnects
  -> transport detects loss
  -> no simulation-side state transition
  -> run continues headlessly
  -> client reconnects
  -> client requests/receives latest committed identity
  -> rendering resumes
```

No synthetic WAIT, no agent death, and no censoring event may be caused by Observatory disconnect.

## Initial implementation scope

The first Observatory implementation may operate over:

- recorded smoke/pilot evidence; and/or
- an in-process or local sidecar post-commit projection stream.

It does not need to wait for full durable crash/resume admission as long as the live projection remains non-authoritative and headless execution is preserved.

## Test obligations

- projector runs only after commit;
- same committed input yields deterministic frame identity;
- duplicate delivery is idempotent in the client state reducer;
- stale delivery cannot roll the displayed committed state backward silently;
- skipped live frames are detectable;
- client disconnect/reconnect does not alter canonical hashes/events;
- detail evidence is resolved by immutable reference;
- replay controls do not trigger inference or mutation.
