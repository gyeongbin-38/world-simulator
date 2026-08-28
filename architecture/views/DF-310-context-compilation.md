# DF-310 — Context Compilation

**Status:** REVIEWED  
**Parent:** ARC-300  
**Freeze state:** IMPLEMENTATION-READY  
**Question:** How is one deterministic, traceable ContextPack compiled from a bound canonical snapshot?

## Deterministic flow

```text
immutable S_t
+ committed agent-visible events/artifacts
+ ContextPolicy version
+ action-presentation version
        ↓
visibility projection
        ↓
provenance attachment and deduplication
        ↓
personal-history selection
        ↓
neutral deterministic ordering
        ↓
immutable ContextPack
        ↓
ContextPack hash and durable ArtifactRef
```

Identical bound snapshot, opportunity identity, source evidence, and policy
versions must produce the same structural ContextPack and `context_hash` before
model-specific rendering. Database query order, inference completion order,
process restart, cache state, and wall time are excluded inputs.

## Compiler inputs

The compiler accepts only explicit, versioned inputs:

- the exact immutable `S_t`, state version, and state hash;
- one cognition opportunity identity and its agent identity;
- committed State/Event/Artifact records available no later than `S_t`;
- a frozen `ContextPolicy` including history and ordering rules;
- the versioned action-presentation reference;
- an ordering seed identity/digest derived under INV-32.

It does not query analysis labels, UI state, global transcript text, another
run's cache, or model-authored semantic memory.

## Visibility projection

The compiler uses positive inclusion rules. It does not serialize a canonical
object and then attempt to redact fields.

For agent `a` at `S_t`:

1. self projection contains only `a`'s opaque ID and active age;
2. peer directory contains active IDs in `S_t` except `a`;
3. a directed message is newly delivered only when its recipient is `a` and
   its committed availability boundary is `S_t`;
4. an earlier message is history-eligible only when `a` was sender or recipient;
5. a pending proposal is visible only when `a` is its proposer or its addressed
   target and LC-220 says it is visible in `S_t`;
6. a terminal proposal or resolution is history/outcome-eligible only for its
   participants and only from a committed source;
7. a committed own-action outcome may be projected neutrally, but a failed or
   uncommitted proposal cannot be presented as successful;
8. event/artifact records without an explicit ARC-300 visibility projection are
   excluded even if they are easy to query.

Raw event names, commit metadata, ticks, ordering keys, source hashes, and
ArtifactRefs remain provenance unless a model-visible projection explicitly
requires their payload.

## Provenance and deduplication

Every model-visible projection has exactly one or more explicit source
references. Provenance identifies the projection's stable structural path in
the finalized pack, record class, source ID, bound state version, committed
tick/order when applicable, and immutable ArtifactRefs when exact bytes are
required. The structural path/source metadata is not rendered to the model.

Deduplication uses `(projection_kind, source_kind, source_id)` and occurs before
history limits. The same projection cannot appear in multiple ContextPack
regions. Region precedence is:

```text
visible current protocol
> newly delivered information
> prior personal-visible history
```

Different safe projections from one committed source require distinct
`projection_kind` values and separate provenance entries; they cannot be
created through free-form compiler interpretation.

## Personal-history selection

Mandatory current categories are assembled first and are outside the prior
history limit. Prior history candidates must be committed, self-visible, not
already deduplicated into a current region, and no earlier than the agent's
first active boundary.

Selection is exact:

1. group candidates by committed tick from newest to oldest;
2. within a tick, use the non-causal ordering rule unless an owner-defined
   dependency gives genuine causal order;
3. take at most `max_prior_visible_records` candidates;
4. present the selected groups oldest to newest while preserving the frozen
   within-group order.

No summary, embedding similarity, semantic importance score, social score, or
model-authored preference affects selection. `0` is valid and means no prior
history beyond mandatory current information.

## Ordering neutrality

Chronological ordering is retained between distinct committed tick groups.
Items in the same visible boundary have no priority merely because a database,
agent ID, event table, worker, or model runtime returned them first.

For each unordered category, the baseline rank is the ascending digest of:

```text
ALIFELM_CONTEXT_ORDER_V1
|| ordering_seed_digest
|| run_id
|| opportunity_id
|| bound_tick
|| category
|| stable_item_key
```

using SHA-256 over the machine contract's canonical UTF-8 encoding. The
ordering seed is pinned experiment metadata derived only from frozen causal
identities. It is researcher-only and is not rendered into model text.

The tick/opportunity binding prevents a stable low-ID positional privilege from
persisting across opportunities. Hash ties, however improbable, are broken by
the full stable item key. The policy version and seed identity are included in
ContextPack evidence and context identity.

## Canonicalization and hash

`ALIFELM_CONTEXT_CANONICAL_JSON_V1` uses UTF-8 JSON, lexicographically sorted
object keys, no insignificant whitespace, and arrays already ordered by this
view. `context_hash` is SHA-256 over:

- ContextPack schema version;
- bound run/opportunity/snapshot identity and state hash;
- ContextPolicy and action-presentation identities, versions, and resolved
  contract digests;
- ordering policy identity;
- the complete model-facing structural region;
- source provenance and required ArtifactRefs.

Later rendered token count, cache hits, worker placement, model profile,
generation seed, retry count, and wall-clock metadata are excluded from
`context_hash`. A full serialized artifact digest may still cover the complete
immutable envelope.

## Durability and restart

In confirmatory execution, the finalized ContextPack structure and hash become
a durable content-addressed artifact before model inference is submitted. Raw
model output and later cognition lineage reference that exact ContextPack
artifact. A crash may leave an unreferenced ContextPack artifact, which is an
allowed ARC-270 orphan and not canonical state.

On restart, the compiler rebinds the same durable `S_t`, opportunity, policies,
and ordering identity. It must reproduce the same `context_hash` and resolve or
deduplicate the existing artifact. Restart timing does not create a new context,
tick, history item, or cognition opportunity.

## Research-only telemetry

Per opportunity, retain outside the model-facing region:

- ContextPack hash and ArtifactRef;
- ContextPolicy and action-presentation identities/versions;
- ordering policy version and seed identity;
- count of visible records by category;
- exact source references and deduplication/selection counts;
- later, tokenizer profile and rendered input token count;
- later, runtime cache telemetry.

Telemetry is evidence, not simulation state and not agent-visible context.

## Acceptance specification for ContextCompiler

Before real model integration, the executable conformance suite must include:

1. `peer_private_history_never_leaks`
2. `hidden_lineage_never_leaks`
3. `hidden_birth_seq_never_leaks`
4. `researcher_labels_never_leak`
5. `same_tick_peer_output_never_leaks`
6. `uncommitted_intent_never_leaks`
7. `newborn_has_no_parent_history`
8. `own_delivered_message_is_visible`
9. `other_agents_directed_message_is_hidden`
10. `proposal_visible_only_to_allowed_participant`
11. `identical_inputs_produce_identical_context_hash`
12. `storage_query_order_does_not_change_context`
13. `inference_completion_order_does_not_change_context`
14. `neutral_peer_order_has_no_low_id_priority`
15. `context_contains_only_traceable_committed_sources`
16. `sprite_identity_not_visible_in_EXP000`
17. `no_model_written_semantic_memory_in_baseline`
18. `action_presentation_is_version_pinned`
19. `policy_change_changes_context_identity`
20. `restart_reload_produces_identical_context` (the executable form of the
    requested `restart/reload_produces_identical_context` criterion)

The suite must use at least three storage/source enumeration permutations and
three inference-completion permutations. Neutral-order testing must verify that
lexically/numerically low opaque IDs do not systematically occupy the first
position across multiple opportunity/tick bindings.

## Cross-validation

| Owner | Result |
|---|---|
| A00 / ARC-010 | Positive visibility projection preserves minimal social priors, private boundaries, hidden lineage, and researcher-only metadata. |
| ARC-200 / SEQ-230 | P3 binds every pack to the same `S_t`; compilation cannot observe P4 outputs. |
| ARC-240 | Final ContextPack is immutable evidence; compiler candidates remain protocol work; neither mutates AgentState. |
| LC-210 | Age is a projection only; newborn history begins at first activation and inherits nothing. |
| LC-220 | Proposal creation, target visibility, participant scope, and successful/failed resolution are not reinterpreted. |
| DF-260 | Every rendered item traces to committed evidence and the exact model input is retained for qualitative claims. |
| ARC-270 / SEQ-250 | Durable ContextPack identity follows CAS/orphan/restart rules and is reused across infrastructure retry. |
