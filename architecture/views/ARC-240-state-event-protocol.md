# ARC-240 — State, Event, Artifact & Protocol

**Status:** REVIEWED  
**Parent:** ARC-200  
**Question:** What is current truth, historical fact, immutable evidence, and transient work?

## STATE

Mutable current simulation truth.

Examples:
- run status/current tick;
- living agent state;
- message delivery state;
- pending proposal state;
- applied intervention state.

State answers:

> What is true now?

## EVENT

Immutable historical fact associated with a committed transition or other classified record.

Examples:
- agent born;
- agent died;
- message committed;
- reproduction proposal committed/resolved;
- intervention applied;
- tick committed.

Event answers:

> What happened?

Event order is causal only through committed ordering metadata, never wall-clock timestamps.

## ARTIFACT

Immutable evidence/payload identified by stable identity/digest.

Examples:
- raw model output;
- selected ContextPack;
- message body payload;
- intervention payload;
- derived registered dataset.

Artifact answers:

> What exact bytes/evidence were used or produced?

## PROTOCOL

Non-authoritative request/candidate/work object that may fail.

Examples:
- cognition request;
- ActionIntent;
- ValidatedIntent;
- birth candidate;
- transition fragment;
- CommitRequest.

Protocol answers:

> What is being proposed/evaluated?

## Atomic boundary

```text
raw required evidence durable/identified
        ↓
validate / resolve
        ↓
expected state version check
        ↓
canonical state mutation
+ required domain event/outbox
        ↓
atomic commit
        ↓
next snapshot publication
```

Failed proposals must not fabricate successful domain events.

## Rules

```text
PERSISTED != CANONICAL STATE
GENERATED != COMMITTED
EVENT != CURRENT STATE
SNAPSHOT != MUTABLE STATE
ANALYSIS != SIMULATION TRUTH
```

Live authority is canonical materialized state. Historical scientific evidence is committed events plus immutable referenced artifacts.
