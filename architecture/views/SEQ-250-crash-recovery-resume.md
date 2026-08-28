# SEQ-250 — Crash Recovery & Resume

**Status:** REVIEWED  
**Parent:** ARC-200  
**Gate:** D0  
**Freeze state:** IMPLEMENTATION-READY  
**Question:** How does a process restart resume a run without creating a partial canonical boundary or a new causal opportunity?

## Recovery invariant

Recovery first resolves the last durable commit identity. It does not infer
from process memory, wall-clock duration, an outbox acknowledgement, or a
partial transient work directory.

```text
commit not durably confirmed → canonical truth is S_t
commit durably confirmed     → canonical truth is S_(t+1)
```

There is no canonical `S_t+0.5`. A crash is infrastructure state, not an
agent death, not a natural-lifespan tick, and not a reason to create a new
cognition opportunity for an already committed boundary.

## Failure-point policy

| Failure Point | Durable facts | Non-durable work | Restart behavior | Model re-call? | Same seed? | Commit retry? |
|---|---|---|---|---|---|---|
| F1. cognition start | Current committed `S_t`, run config, and reproducibility identities | Bound opportunity and in-process scheduling work | Read `S_t`, reconstruct the same opportunity set, then start the pending tick | No prior generation exists; call only as a new attempt under policy | Yes, derive from stable run/agent/opportunity identity | No |
| F2. model inference running | `S_t`; optional attempt identity only | In-flight request and incomplete output | Discard in-flight process state; retry the same cognition request only under the frozen failure policy | Yes, only because no valid raw output is durable | Yes | No |
| F3. raw output generated, parse not complete | `S_t`; verified raw ArtifactRef if artifact durability completed | Unverified/incomplete artifact or parser state | If ArtifactRef resolves, parse that exact bytes; otherwise follow pre-raw-output retry policy | No when raw ArtifactRef resolves; otherwise Yes under policy | Yes | No |
| F4. parsed ActionIntent, validation not complete | `S_t` and required raw ArtifactRef; parsed value may be recomputed | Parsed object and validation work | Re-read/reparse the exact raw artifact and validate against the same `S_t` | No | N/A for replayed raw evidence | No |
| F5. validated TransitionFragment, commit not started | `S_t`, required ArtifactRefs, deterministic request identity if staged | Fragments and in-memory commit request | Rebuild or load the same request, compute the same `commit_id`, then submit once | No | N/A | Yes, same `commit_id` only |
| F6. DB transaction started, state write in progress | Prior committed boundary; uncommitted transaction is not visible | Open transaction and partial engine buffers | Database recovery rolls back an uncommitted transaction; verify `commit_id`, then retain `S_t` or return the committed result | No | N/A | Lookup, then same-ID retry only if absent |
| F7. state write and required event/outbox write | Prior committed boundary; no logical partial commit may be visible | Transaction-local state/event/outbox writes | Atomic transaction resolution exposes either all required records or none; never repair by fabricating an event | No | N/A | Lookup, then same-ID retry only if absent |
| F8. COMMIT requested, success unknown | Either prior boundary or the complete committed unit, depending on transaction outcome | Process acknowledgement and in-memory publication | Query `commit_id` and expected version/hash; classify existing commit or retry the same request | No | N/A | Lookup first; never blind retry |
| F9. transaction succeeded, acknowledgement lost | Complete `S_(t+1)`, events, outbox, metadata, and artifact references | Success acknowledgement | Lookup returns the existing commit and result; republish locally if needed | No | N/A | No duplicate retry; same-ID lookup only |
| F10. `S_(t+1)` publication in progress | Durable committed `S_(t+1)` and commit metadata | Process-local cache/publication marker | Reload the durable boundary and idempotently publish the already committed snapshot | No | N/A | No; commit is already known |
| F11. artifact write/hash verification | Prior canonical boundary; only verified artifacts are commit-eligible | Temporary bytes, incomplete hash, staging marker | Verify/resume the same bytes or discard the stage; an unresolved ArtifactRef blocks commit | No if exact raw bytes are recoverable; otherwise Yes only under pre-raw-output policy | Yes when retry is allowed | No until artifact precondition succeeds |
| F12. recovery/replay crashes | Last verified committed boundary, metadata, event history, and durable artifacts | Recovery cursor, replay cache, and process-local checkpoint | Restart from the last verified boundary; repeated recovery/replay is idempotent; corruption becomes explicit run failure/deviation | No | N/A | Lookup only; no blind transition retry |

`N/A` means that no model generation is being created at that recovery step.
An answer of `Yes` is permitted only before a valid raw output is durable and
only under the existing cognition failure policy.

## Critical cognition rule

Once valid raw output is durable, it is the evidence for that cognition
opportunity. Infrastructure retry must not silently call the model again and
replace it. Parsing, validation, transition planning, commit lookup, and
recovery all reuse the exact ArtifactRef.

If the failure occurs before valid raw output is durable, a confirmatory retry
is allowed only with:

```text
same ContextPack identity
same generation seed
same generation policy
same model profile
same opportunity/request identity
```

Retry count, restart timing, process ID, worker assignment, GPU completion
order, and wall-clock pause are excluded from causal seed material.

## Commit ambiguity protocol

The process must never infer transaction success from its own last instruction
or from a publication acknowledgement. After restart, it queries the durable
adapter by `commit_id` and verifies:

```text
run_id
tick
state_version_before / after
previous_state_hash
resulting_state_hash
transition_digest
```

Outcomes are:

- exact matching commit exists: return it and do not apply anything again;
- no commit exists and the prior version/hash still matches: retry the same
  request with the same `commit_id`;
- same identity has different content, or the version/hash has an unexpected
  value: stop with explicit corruption/deviation; do not choose a winner or
  fabricate a state/event pair.

Unique durable identities prevent duplicate births, messages, proposals,
events, and outbox records even when the acknowledgement was lost.

## Tick recovery and run status

Recovery never consumes a simulation tick. If a partial cognition or commit
attempt remains while the last confirmed boundary is `S_t`, the run resumes
from `S_t` and preserves all LC-210/LC-220 timing facts. In particular:

- no agent is killed by a process crash or database rollback;
- natural death is evaluated only by the committed lifecycle transition;
- final-tick actions are not discarded because publication failed;
- a successful birth is not replayed as a new cognition opportunity;
- proposal visibility and newborn activation do not move because of downtime.

Operational recovery state is separate from ecological/run outcome state. The
adapter may expose `RECOVERING` while process repair is in progress. An
irrecoverable integrity failure must end in explicit `FAILED_CORRUPTION` (or an
equivalent recorded deviation) with the failing commit identity and evidence
scope. It must never be reported as normal `FINISHED`, capacity censoring, or
agent death.

Capacity remains an explicit censoring outcome under the existing SEQ-230 and
Constitution rules. A storage or process failure is not capacity censoring
unless the configured capacity boundary was actually reached.

## Replay versus replication

Replay reads the initial boundary, committed state/event history, commit
metadata, and required artifacts. It performs no model inference, does not
create a new run, and must reproduce the recorded state hash at each checked
boundary.

Replication creates a fresh `SimulationRun`; it may perform fresh model
inference under a separately frozen condition. A replay failure cannot be
repaired by silently switching to replication.

## Adapter-neutral requirements

SQLite/WAL is only a reference implementation candidate. Any durable adapter
must preserve:

1. compare-and-commit against expected state version and previous state hash;
2. atomic state/event/outbox/commit metadata visibility;
3. idempotent `commit_id` lookup and retry;
4. immutable ArtifactRef preconditions;
5. durable boundary and hash verification for replay;
6. explicit corruption/deviation status.

## D0 acceptance tests for I-03

The following names are the minimum acceptance suite. They are deliberately
specified before persistence code exists:

1. `crash_before_commit_preserves_prior_state`
2. `crash_during_transaction_has_no_partial_transition`
3. `committed_state_never_lacks_required_event`
4. `committed_event_never_claims_uncommitted_state`
5. `retry_same_commit_is_idempotent`
6. `duplicate_commit_does_not_duplicate_birth`
7. `duplicate_commit_does_not_duplicate_message`
8. `duplicate_commit_does_not_duplicate_proposal`
9. `committed_artifact_ref_always_resolves`
10. `orphan_artifact_does_not_become_canonical`
11. `restart_after_unknown_commit_result_detects_existing_commit`
12. `replay_reconstructs_identical_state_hash`
13. `replay_does_not_call_model`
14. `wall_clock_pause_does_not_advance_simulation_tick`
15. `crash_does_not_kill_agents`
16. `repeated_recovery_is_idempotent`
