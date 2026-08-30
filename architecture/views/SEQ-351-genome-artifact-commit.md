# SEQ-351 — N0 Child Genome / Birth Commit

**Status:** REVIEWED  
**Parent:** ARC-350  
**Gate:** N0  
**Alias:** SEQ-N0  
**Freeze state:** IMPLEMENTATION-READY  
**Question:** How does one eligible bilateral birth acquire a canonical child genome without a partial committed child after crash?

## Preconditions

This sequence applies only in a later neural-heredity experiment. LC-220 has
already produced a successful eligible bilateral `BirthPlan`; parent choice and
same-boundary conflict resolution are complete before genome construction.
EXP-000 bypasses this sequence and retains `NullGenome` birth semantics.

The BirthPlan binds `run_id`, `tick`, deterministic `child_birth_seq`, opaque
child identity, reproduction event identity, the two selected parent genome
references, and the manifest/policy versions required by ARC-350.

## Authoritative sequence

```text
ReproductionService       GenomeInheritance        CAS          P11 / SQLite-WAL       Publisher
        |                         |                  |                    |                  |
        |-- validated BirthPlan ->|                  |                    |                  |
        |                         |-- C0 validate -->|                    |                  |
        |                         |-- canonicalize parent genome order    |                  |
        |                         |-- derive named deterministic RNG      |                  |
        |                         |-- construct ideal effective target    |                  |
        |                         |-- mutate if manifest-pinned           |                  |
        |                         |-- reference factorize/materialize     |                  |
        |                         |-- save canonical child bytes -------->|                  |
        |                         |<------------- durable ArtifactRef ----|                  |
        |                         |-- resolve + verify SHA-256 ---------->|                  |
        |<-- child genome + GenomeEvidence ------------------------------|                  |
        |-- CommitRequest: child state, BirthCommitted, lineage edges, -------------------->|
        |   genome_ref/metadata, researcher-only genome event, outbox rows                  |
        |                         |                  |               BEGIN IMMEDIATE          |
        |                         |                  |               compare version/hash     |
        |                         |                  |               verify durable refs       |
        |                         |                  |               write all rows            |
        |                         |                  |               COMMIT                    |
        |<-------------------------------------------------------- CommitResult              |
        |------------------------------------------------------------------------ publish -->|
```

No canonical `child-without-genome` intermediate state exists. P11 atomically
commits child `AgentState`, `BirthCommitted`, researcher lineage edges, child
`genome_ref`, genome metadata/event, commit metadata, and required outbox rows.
Publication occurs only after the database transaction is durably confirmed.

`H0_NULL` has no tensor artifact, but its deterministic `NullGenome`
identity and metadata must still be in the atomic transaction. A
`H0_RESET_ZERO` birth passes through `GenomeInheritance` and assigns the
base-bound `ZERO_ADAPTER` sentinel without parental contribution or mutation.
A `ZERO_ADAPTER` sentinel may omit physical tensor bytes; P11 verifies its
deterministic descriptor/digest and base binding. Every non-sentinel
`AdapterGenome` requires a resolved durable CAS artifact before P11 begins.

## Failure and retry matrix

| Failure | Durable result | Retry rule |
|---|---|---|
| Before genome construction | Existing `S_t` only | Rebuild the same BirthPlan and RNG identities |
| During construction | Existing `S_t`; transient work only | Discard work and reconstruct on the pinned reference backend |
| After CAS put, before P11 | Existing `S_t` plus allowed orphan artifact | Resolve/deduplicate the same digest; never allocate a new genome identity |
| During P11, outcome unknown | Either complete old boundary or no boundary | Lookup deterministic `commit_id`; return exact committed result or retry the same request |
| After P11, before publish | Complete `S_(t+1)` | Republish the committed snapshot; no new birth or genome event |
| Committed reference fails CAS verification | Corruption/deviation | Fail closed; do not publish or continue the run as valid |

Retry count, wall time, UUID randomness, process identity, worker selection,
and completion order are excluded from birth, genome, artifact, event, and
commit identities.

## Required invariants

- A precommit orphan genome artifact is safe and non-canonical.
- A committed non-sentinel child referencing missing or mismatched required
  genome bytes is forbidden.
- Parent/base artifacts and parent genomes are immutable throughout.
- The same causal inputs reconstruct the same child factors, effective digest,
  GenomeEvidence, artifact bytes, and commit identity.
- Genome evidence is researcher-only and is never rendered into ContextPack.
- The child first participates at `t+1`, unchanged from LC-210/SEQ-230.

## Owner boundaries

- LC-220 owns selection, eligibility, and successful BirthPlan creation.
- ARC-350 owns genome laws, compatibility, RNG, evidence semantics, and
  backend authority.
- ARC-270/SEQ-250 own general durable commit and crash recovery behavior.
- This sequence owns only the N0 artifact-before-birth ordering and atomic
  genome references.
