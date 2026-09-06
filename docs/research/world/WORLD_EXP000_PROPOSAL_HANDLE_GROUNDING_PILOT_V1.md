# WORLD EXP-000 Proposal Handle Grounding Pilot V1

Status: **PREREGISTERED / NO NEW MODEL FORWARD YET**

## 1. Purpose

The first LIVE EXP-000 multi-agent pilot completed with intact infrastructure but zero births. A read-only audit accounted for all eight LawValidator rejections and confirmed three payload-side proposal-reference failures in which a compatible canonical proposal identifier was visible verbatim to the model, yet the generated `proposal_id` was generic or invented.

This pilot tests one narrow interface intervention: **context-local proposal handles during the already-selected ACCEPT/REJECT payload stage only**.

It does not change action selection, action availability, world laws, target-agent grounding, model weights, or the canonical proposal identifiers stored in simulation state.

## 2. Frozen source evidence

- LIVE pilot execution commit: `55b4c5128a40c2e68a6a7cc205424e7e6a802314`
- LIVE pilot result digest: `b82267d7769cbc4dc56aaa3c5f82e5e66b1b669ef407b4c58d1a994b4ae29f00`
- LIVE pilot canonical archive SHA-256: `b9d6e31df6e01e1ddabd943b40601255c7d80361b3eb5b3c217f25f5cc5b36e3`
- proposal-reference visibility audit commit: `552b7ee9a0c7dd267e3621227350b9d3a9b542d6`
- C10 score-selected runtime remains the accepted architecture from the parent pilot.

Observed law-rejection partition:

- `SEND / SELF_TARGET`: 1
- `ACCEPT / UNKNOWN_PROPOSAL_ID`: 6
- `REJECT / UNKNOWN_PROPOSAL_ID`: 1

Of the seven proposal-reference failures, three occurred with one or more compatible incoming pending proposals visibly present in the model-facing context. Four occurred when no compatible incoming proposal existed and are classified as a separate action-availability problem.

## 3. Frozen intervention boundary

### 3.1 Score and action selection remain unchanged

For every cognition opportunity the score stage remains exactly:

- WORLD prefill: FA-v1;
- action branch scoring: BASE;
- five-action order: `WAIT`, `SEND`, `PROPOSE`, `ACCEPT`, `REJECT`;
- score: existing mean branch log probability;
- temperature: exactly `T=1.0`;
- categorical variate: existing deterministic opportunity-identity SHA-256 rule.

The proposal-handle layer is unreachable until after an action label has already been selected.

### 3.2 Actions affected

Only payload generation for already-selected `ACCEPT` and `REJECT` may use the proposal-handle treatment.

- `WAIT`: unchanged; no payload stage.
- `SEND`: unchanged canonical rendering/schema.
- `PROPOSE`: unchanged canonical rendering/schema.
- `ACCEPT`: proposal-handle payload treatment when visible proposal references exist.
- `REJECT`: proposal-handle payload treatment when visible proposal references exist.

Agent IDs are not aliased in V1. This pilot therefore does not address the observed self-target SEND failure.

### 3.3 Deterministic proposal-handle map

For one compiled context, collect proposal identifiers already present in the model-visible `ModelInput`, in deterministic first-occurrence order across:

1. `newly_delivered`;
2. `visible_protocol_state`;
3. `prior_history`.

Every distinct visible proposal identifier is assigned one local opaque handle:

`R0`, `R1`, `R2`, ...

Only the model-facing rendered proposal identifier is replaced. Counterparty/peer agent identifiers remain unchanged. The immutable `ContextPack`, canonical Snapshot, SQLite state, proposal records, and proposal IDs remain unchanged.

### 3.4 Reference-domain constraint, not law-eligibility filtering

When at least one visible proposal handle exists and the selected action is ACCEPT or REJECT, the forced payload schema constrains `proposal_id` to the set of **all visible proposal handles**, not merely currently law-admissible incoming pending proposals.

Therefore the intervention may eliminate invented/unknown proposal identifiers, but it does not guarantee legal action. The model may still choose:

- an outgoing proposal;
- a resolved or otherwise ineligible visible proposal;
- a proposal addressed to another actor if such a reference is visible under the existing context policy.

`LawValidator` remains the only authority for whether the mapped canonical proposal is admissible.

This reference-domain constraint must not be described as evidence of improved autonomous proposal-ID copying competence; it is an explicit interface grounding intervention.

### 3.5 No-handle behavior

If an already-selected ACCEPT/REJECT opportunity contains no visible proposal identifier, V1 uses the existing baseline payload path unchanged. It does not invent a synthetic handle, convert the action to WAIT, retry, resample, or suppress the selected action.

This preserves the separate action-availability failure mode for later study.

### 3.6 Handle resolution

A generated handle is resolved deterministically to the associated canonical proposal ID before `CognitionGateway` binding.

The Gateway and LawValidator receive canonical IDs only. No handle is canonical simulation state.

## 4. Evidence requirements

For every handle-treated payload attempt preserve:

- original ContextPack ArtifactRef;
- proposal-handle rendered input bytes/ref;
- exact ordered handle map;
- forced action label;
- allowed handle set;
- raw generated text containing the model-facing handle;
- parsed handle candidate;
- mapped canonical candidate;
- Gateway-bound canonical intent, if binding succeeds;
- LawValidator result;
- phase trace and generation identity.

No raw evidence may be overwritten after the first model forward.

## 5. First GPU validation

Before any new continuous live run, run a bounded **source-trajectory grounding smoke** against the three previously observed eligible failures only:

- tick 2 / `EXP000_FOUNDER_A` / frozen action `ACCEPT`;
- tick 8 / `EXP000_FOUNDER_A` / frozen action `ACCEPT`;
- tick 14 / `EXP000_FOUNDER_C` / frozen action `REJECT`.

The smoke reconstructs each exact source snapshot/context from the sealed R1 durable evidence, verifies source context identity, and executes only the already-selected payload stage with the proposal-handle intervention. It performs no simulation commit and does not rerun the action selector.

Primary infrastructure gates:

- exact source context/snapshot identity verified;
- handle map deterministic and non-empty;
- only proposal IDs are aliased;
- forced action remains the frozen source action;
- generated proposal reference is a permitted local handle;
- handle resolves to an exact canonical source proposal ID;
- Gateway receives the canonical mapped candidate;
- no retry/fallback/resampling/action rewrite;
- snapshot unchanged;
- weight updates `0`.

LawValidator admission is descriptive, not a primary pass threshold, because the handle domain intentionally includes visible but potentially ineligible proposals.

## 6. Follow-up live pilot boundary

Only after CPU admission and the bounded source-trajectory grounding smoke pass may a new versioned continuous LIVE EXP-000 pilot be preregistered.

The follow-up live pilot must not silently add action-availability masking. If ACCEPT/REJECT is selected with no compatible proposal, the existing failure semantics remain observable.

## 7. Interpretation bounds

A successful proposal-handle pilot would establish that a context-local reference interface can remove the specific long opaque-ID generation failure while preserving canonical world authority and the frozen action selector.

It would not establish:

- calibrated action availability;
- autonomous reproduction competence;
- semantic selection of the best proposal;
- social intelligence;
- evolutionary adaptation;
- neural heredity.
