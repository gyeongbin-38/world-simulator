# ARC-270 — Durable Commit & Replay Boundary

**Status:** REVIEWED  
**Parent:** ARC-200  
**Gate:** D0  
**Freeze state:** IMPLEMENTATION-READY  
**Question:** Which durable boundary keeps canonical state, required evidence, committed facts, and publication unambiguous after a process crash?

## Scope

This view freezes the semantics required before durable persistence and replay are
implemented. It does not select a database schema, WAL configuration, CAS
product, filesystem layout, or deployment topology. SQLite/WAL is a possible
adapter implementation, not an architecture authority.

The live in-memory I-02 commit boundary remains the semantic reference. A
durable adapter must preserve its state-version, event, visibility, lifecycle,
reproduction, capacity, and ordering rules.

## Authority and record classes

| Record or service | Classification | Authority and durability rule |
|---|---|---|
| Live canonical materialized state | STATE | The current state for a run is the versioned materialized value selected by the validated commit boundary. A database row, cache, or stale process copy is not authoritative merely because it is persisted. |
| Committed event history | EVENT | Immutable historical facts produced by a committed transition. Events are committed with the state transition and are never used to silently invent a missing state mutation. |
| Raw model output and other required evidence | ARTIFACT | Immutable bytes addressed by verified content identity. The artifact store is evidence storage, not simulation state, memory, or a model authority. |
| Transaction outbox | PROTOCOL | A durable post-commit delivery obligation created in the same logical commit. Delivery, acknowledgement, and retry status are operational facts and cannot change simulation causality. |
| Snapshot | STATE VALUE / CHECKPOINT | An immutable representation of one committed boundary, useful for reads, replay checkpoints, and context compilation. It is not a mutable state owner. |
| ActionIntent, ValidatedIntent, BirthCandidate, TransitionFragment, CommitRequest | PROTOCOL | Non-authoritative work that may fail. A retry or durable work record cannot become canonical without the commit boundary. |
| Commit metadata | EVENT | The immutable boundary fact containing the identity and hashes that bind one logical state transition to its event and outbox records. It is not a second simulation state. |

The classification preserves the ARC-240 rules:

```text
PERSISTED != CANONICAL STATE
GENERATED != COMMITTED
EVENT != CURRENT STATE
SNAPSHOT != MUTABLE STATE
```

D0 adds no fifth record class: an outbox row is durable protocol work, while
commit metadata is event-associated boundary metadata.

## Durable commit unit

For an open tick `t`, the durable adapter performs one logical atomic commit:

```text
verify expected state version and previous state hash
        ↓
verify all required ArtifactRefs resolve to immutable bytes
        ↓
verify deterministic CommitRequest / transition digest
        ↓
write canonical state S_(t+1)
write required domain events and their causal order
write required outbox records
write CommitMetadata
        ↓
one database transaction commit
        ↓
publish the immutable S_(t+1) value
```

The transaction must have all-or-nothing visibility. In particular, the
following states are forbidden:

```text
canonical state updated but a required event is missing
event claims a commit whose canonical state transition is absent
outbox claims a commit that the commit metadata does not contain
```

An adapter may use separate physical tables or storage engines internally, but
the externally observable commit contract remains one logical atomic boundary.

## Commit identity and ordering

Each successful tick commit has the following minimum durable metadata:

| Field | Meaning |
|---|---|
| `commit_id` | Stable idempotency identity for one logical request. It is derived before the first attempt from run identity, tick, expected version/hash, and canonical transition digest. Retry timing and retry count are excluded. |
| `commit_seq` | Per-run successful commit sequence. For the baseline one-tick progression, it equals `state_version_after`; it is assigned once and never changes on retry. |
| `run_id` | Run identity. |
| `tick` | The open tick whose transition produced the next boundary. |
| `state_version_before` | Expected version of `S_t`. |
| `state_version_after` | Version of the committed `S_(t+1)`; it must be `state_version_before + 1`. |
| `previous_state_hash` | Hash of the exact canonical `S_t` used by validation/planning. |
| `resulting_state_hash` | Hash of the exact canonical `S_(t+1)` published by the commit. |
| `transition_digest` | Deterministic digest of the validated, canonically ordered transition request. |
| `event_count` and event ordinals | Count and zero-based causal order of events in this commit. Event order is deterministic serialization after domain conflict resolution, never wall-clock or completion order. |

`commit_id`, `(run_id, state_version_after)`, and the transition digest are
unique constraints at the adapter boundary. A request with an existing
`commit_id` is an idempotent lookup only when its immutable request identity
matches. A same-ID/different-payload request is a corruption/deviation and is
not applied.

Idempotent retry guarantees:

- no duplicate state transition;
- no duplicate domain event;
- no duplicate outbox record;
- no duplicate child, message, or proposal;
- no causal effect from retry count, process uptime, wall-clock delay, or
  storage completion order.

The adapter returns the already committed result for an identical retry. It
does not run cognition again and does not allocate a new commit sequence.

## Required raw artifact protocol

Required raw output is evidence for the generated/validated behavior. It must
become an addressable, hash-verified durable artifact before a commit may
reference it:

```text
raw bytes produced
        ↓
stage bytes outside the canonical DB transaction
        ↓
verify content digest, byte length, and artifact contract
        ↓
publish immutable ArtifactRef as DURABLE
        ↓
DB commit may reference that ArtifactRef
```

The artifact store and database do not need a shared filesystem transaction.
The precondition is stronger and explicit: a required `ArtifactRef` must
resolve to the exact immutable bytes before the database transaction starts.
The database must reject a reference that is missing, hash-mismatched, or only
staged.

An artifact can be durable and unreferenced if the process crashes before the
database commit. Such an orphan is evidence storage that may be retained or
garbage-collected under a later explicit policy; it is not canonical state.
The inverse is forbidden: a committed event or commit metadata may not refer
to a missing required artifact. Artifact deletion is never allowed while a
committed reference still resolves to it.

Raw evidence that is durable before parsing is reused for parsing and
validation. Infrastructure retry must not replace it with a new generation.

## Snapshot and publication

`S_t` is the exact immutable canonical value bound before cognition. A commit
for tick `t` creates one immutable `S_(t+1)` with:

```text
S_(t+1).state_version = commit.state_version_after
S_(t+1).state_hash    = commit.resulting_state_hash
```

The durable materialized state is the live state owner after commit. A
`Snapshot` is a value/checkpoint of that boundary: readers may use it for
replay verification and bounded context compilation, but no reader, cache,
artifact, event consumer, or model runtime may mutate it. Publication after a
successful DB commit is a retryable visibility operation; it cannot create a
new canonical boundary or advance the tick.

If an implementation exposes associated committed events alongside a snapshot,
those values retain `EVENT` classification and are not mutable state fields.
The event view cannot be used to bypass the materialized-state commit boundary.

There is no canonical `S_t+0.5`. Before the transaction is known committed,
the durable truth is `S_t`; after the commit is known committed, the durable
truth is `S_(t+1)`.

## Replay and replication

```text
Replay
= reconstruct an already committed run from its initial boundary,
  committed event history, required ArtifactRefs, and verified snapshots.

Replication
= start a new SimulationRun and perform fresh model inference under a
  reproduced experimental condition.
```

Replay never calls a model, creates a new cognition opportunity, consumes
lifespan, changes proposal visibility, or advances simulation time. It
reconstructs/validates the recorded result and compares state hashes at each
available boundary. A snapshot may be used as a checkpoint, but checkpoint
loading must be hash-verified against the committed metadata.

This is not a silent event-sourcing change. Canonical materialized state
remains the live authority; event history is the immutable historical fact
record and replay evidence. A replay implementation must not reinterpret an
event into a different lifecycle, reproduction, message, capacity, or
visibility rule.

## Storage adapter boundary

The durable adapter must expose semantic operations equivalent to:

1. read the current run boundary and its state hash;
2. lookup `commit_id` before applying a retry;
3. atomically compare expected version/hash and commit state, events, outbox,
   and metadata;
4. read committed snapshots/events/artifact references for replay;
5. publish or republish a committed snapshot idempotently.

SQLite/WAL may implement these operations first. Replacing it with another
adapter is an implementation change only if these preconditions and atomicity
semantics remain unchanged.

## Owner boundaries

- ARC-200 still owns kernel responsibility and the Commit Coordinator boundary.
- ARC-240 still owns State/Event/Artifact/Protocol classification.
- SEQ-230 still owns the tick barrier and one authoritative commit.
- DF-260 still owns raw-evidence and censoring lineage.
- LC-210 and LC-220 retain lifecycle and proposal facts; durable storage only
  records or reconstructs them.

## Cross-validation with F0

| Existing owner | D0 result |
|---|---|
| A00 / Constitution | INV-02, INV-03, INV-04, INV-06, INV-07, INV-08, INV-18, INV-19, INV-20, INV-21, INV-27, INV-28, INV-29, and INV-32 remain unchanged. Recovery is infrastructure bookkeeping, not agent death or new causality. |
| ARC-200 | The Commit Coordinator remains the only authority that publishes a next canonical boundary. A storage adapter implements that responsibility; it does not add a competing kernel authority. |
| ARC-240 | State, Event, Artifact, and Protocol classes are preserved. Durable event history does not replace materialized canonical state with an implicit event-sourcing architecture. |
| SEQ-230 | P11 remains one authoritative commit and P12 remains publication. Unknown commit outcome is resolved by identity lookup, never by a second tick or blind retry. |
| DF-260 | Raw evidence remains addressable before required references are committed; orphan artifacts are not canonical; censoring remains explicit lineage. |
| LC-210 | Lifespan, final cognition, newborn activation, maturity, refractory, and natural death facts are replayed, never advanced by downtime. |
| LC-220 | Proposal visibility, acceptance, conflict rejection, pending/terminal state, and successful birth facts are replayed exactly and never fabricated by recovery. |
| CHANGE_POLICY | I-03 SQLite/WAL or another adapter is a C1 adapter change. It must preserve these contracts and add conformance evidence; it is not permission to change C2 domain semantics. |
| GATES | D0 exit intent is met by the frozen atomicity, restart/replay, and raw-evidence preconditions. Durable implementation remains the I-03 gate. |

The complete D0/I-03 acceptance test list is owned and registered by
SEQ-250. This design stage specifies the tests but does not implement them.
