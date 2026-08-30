# WORLD v0 Live Model Bridge Design v1

Status: IMPLEMENTED / GPU ADMISSION PENDING

This document specifies the first CPU-tested live model bridge for WORLD v0.
GPU admission remains pending. It does not change EXP-000 laws, the
ContextPack contract, the action presentation, or the deterministic kernel.
The bridge is an implementation boundary around the existing model proposal
path.

## Causal path

```text
immutable OLMo base + frozen FA-v1
        ↓ loaded once at run initialization
CompiledContext (P3)
        ↓ rendered model input only
WORLD CandidateModelRuntime (P4)
        ↓ raw generation request
strict parser / codec
        ↓ ModelActionCandidate
CognitionGateway
        ↓ gateway-owned actor, tick, intent identity
ActionIntent
        ↓
LawValidator
        ↓
commit barrier
```

P3 compiles every context from the same snapshot before P4 begins. P4 may
dispatch requests in a batch, but results are collected by opportunity and
canonicalized by actor identity before validation. Completion order, batch
position, wall time, retries, and storage timing must not change a same-tick
canonical result.

## Runtime ownership and visibility

The bridge loads the official OLMo base and the frozen FA-v1 adapter once per
simulation run (or explicitly scoped runtime lifetime), never once per agent.
The loaded base is immutable and the adapter is immutable during a run. A
compiled model input contains only the model-facing `ModelInput` projection:
the opaque self handle, listed opaque peers, permitted visible records, and
the pinned neutral action presentation. It does not contain hidden opportunity
identity, private agent state, lineage, researcher labels, or a complete
snapshot.

The model may emit only a candidate label and payload. It cannot create the
canonical actor ID, tick, opportunity ID, or intent ID. `CognitionGateway`
derives those values from the bound `CognitionOpportunity`; the model-facing
self handle is a visible opaque fact, not canonical identity authority.

## Generation and evidence contract

Each request is built through `generation_request_for` with pinned model,
tokenizer, interface treatment, generation policy, context hash, and seed.
The request identity excludes timing and completion order. The bridge must
persist the raw generation result and rendered input through `ArtifactStore`
before parsing, using the existing `RealCognitionDryRunner` evidence shape or
an equivalent implementation. Raw text is evidence, not canonical state.

Parsing is deterministic and strict. `ModelActionParser` accepts only the
neutral action-label/payload object. Empty, malformed, unknown-label, extra
field, and invalid-payload output becomes a typed rejection/evidence record;
it must never silently become `WAIT`. There is no retry policy in this bridge
until a separately preregistered treatment authorizes one. A rejected output
does not produce an `ActionIntent` or a fallback action.

The bridge records at least:

```text
model/base/adapter/tokenizer digests
generation policy and interface-treatment identities
seed and generation identity
context-pack/rendered-input hashes
raw output ArtifactRef
parse/codec status
```

No raw output is written into SQLite canonical state; only its immutable
artifact reference may be included in the appropriate evidence path.

## Existing boundary audit

The current components already provide most of the required semantics:

| Component | Boundary role | Admission constraint |
|---|---|---|
| `ContextCognitionPipeline` | P3 all-context barrier and P4 collection | retain one-snapshot compile barrier and actor-sorted intents |
| `ContextModelRuntimeAdapter` | request construction and raw-result identity checks | shared with durable live evidence preparation |
| `TransformersModelRuntime` | shared model generation backend | construct once; no per-agent loading |
| `ModelActionParser` | strict syntax and field contract | rejection is not `WAIT` |
| `CognitionGateway` | bind hidden actor/tick/intent identity | remains sole identity authority |
| `typed_codec` | researcher-only codec/domain/commit diagnostics | never use it as an action chooser or canonical committer |
| `action_diagnostics` | finite-label teacher-forced diagnostics | diagnostics only; no action execution |
| `motor_diagnostics` | schema/domain/planning evidence | preserve schema validity vs semantic/domain status |
| interface treatments | versioned neutral I0/I1/I2/I3/I4 treatments | choose only after an explicit treatment decision; no blind constraint |
| `DeterministicKernel` + `LawValidator` | validation and commit barrier | model output remains a proposal |

The existing orchestration module still labels itself “fake
candidate-runtime integration.” That label is an implementation gap, not a
permission to bypass the current contracts.

### Syntax-only mechanism decision

No constrained-decoding mechanism is selected by this design. The first live
slice should use the already-audited strict `ModelActionParser` path with the
existing pinned interface treatment. Optional syntax-only I2 or typed I3
constraints may be evaluated later as explicit researcher treatments after
their token-boundary, label-balance, and social-prior audits. `typed_codec`,
`action_diagnostics`, and `motor_diagnostics` remain analysis/validation
helpers; none autonomously selects an action.

## Batching and determinism

The initial implementation may issue one request per compiled context while
exposing a batch-capable interface. A later batch implementation must prove
per-request equivalence against the single-request path, including raw text,
generation identity, parser result, and resulting actor-sorted `IntentBatch`.
No shared mutable decoder state, cache bleed, or adapter switching may make
the result depend on completion order. A malformed member must be recorded as
rejected without changing the other members or turning into a default action.

## Deployment admission tooling

`tools/world_v0_a40_smoke.py` now provides explicit `--validate-only` and
`--execute` modes. The static preflight checks deployment bytes, tokenizer
semantics, accepted identities, repository commit, and immutable output
manifest policy before the PEFT loader can import or move a model to CUDA.
`PeftTransformersLoader` loads the tokenizer, BF16 base, and frozen FA-v1 once
and returns the concrete `TransformersModelRuntime` used by the live bridge.
Deployment paths remain infrastructure metadata; revisions and digests are
the scientific identity.

## Remaining implementation gap list before GPU admission

1. Run the exact accepted OLMo + FA-v1 configuration in a real headless A40
   smoke; no GPU run has been performed by this slice.
2. Add single-request versus batch equivalence tests before enabling batching.
3. Add a durable-store crash/resume test for the live evidence path.

## Test plan before implementation admission

* load-once and immutable base/adapter digest checks;
* model-visible projection excludes hidden opportunity/private fields;
* P3 completes all contexts before any P4 generation;
* parser accepts only the canonical candidate contract;
* malformed/empty/unknown/extra-field outputs are rejected, never `WAIT`;
* gateway, not the model, supplies actor/tick/intent identity;
* raw evidence is CAS-addressable before parsing and is absent from canonical
  state payloads;
* identical request inputs reproduce identical generation identity/evidence;
* reversed completion orders produce the same actor-sorted intent batch;
* no retry or fallback action occurs;
* law validation and commit remain the only state mutation path;
* single-request and batch paths are byte/effect equivalent;
* headless replay preserves the model/config/tokenizer/context provenance.

## Recommended next commit sequence

1. `ops: run world v0 live bridge A40 smoke` — use the frozen FA-v1/base
   identities and a headless run manifest.
2. `test: prove live bridge deployment admission` — file-digest, crash/resume,
   and runtime determinism checks.
3. `docs: record world v0 GPU admission` — update status only after the A40
   smoke passes without causal or evidence failures.

No population policy, mate preference, interaction reward, or neural heredity
is part of these slices. The bridge only connects model proposals to the
existing deterministic validation/commit boundary.
