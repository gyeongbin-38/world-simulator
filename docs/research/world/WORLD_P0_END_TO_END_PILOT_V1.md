# WORLD P0 End-to-End Multi-Agent Pilot V1

Status: PRE-EXECUTION PREREGISTRATION — FROZEN BEFORE PILOT EXECUTION

## 1. Purpose

P0 tests whether the accepted WORLD-v0 model path can participate in a bounded
multi-agent simulation from cognition through deterministic validation,
canonical commit, durable persistence, and replay verification.

P0 is an infrastructure and causal-integrity pilot.

P0 does NOT test whether agents exhibit interesting social behavior,
cooperation, reproduction, communication, hierarchy, personality,
civilization, or any target action frequency.

A run containing only NO_DIRECTED_ACTION / WAIT behavior may still pass P0.

## 2. Scientific invariants

P0 preserves the existing WORLD invariants:

- no predefined social roles;
- no friendship, trust, rank, team, mate score, or cooperation reward;
- no synthetic affect or personality baseline;
- no initial resources;
- model output is a candidate ActionIntent only;
- deterministic validation and canonical commit remain external to the model;
- private/non-visible state must not enter model-facing context;
- same-tick cognition cannot observe same-tick committed consequences;
- no retry, fallback, output repair, or implicit replacement action;
- rejected cognition is not converted into WAIT;
- replay must not invoke model inference;
- action frequency is descriptive and is never an admission criterion.

## 3. Deployment identity

Model family:
- base: allenai/OLMo-2-0425-1B-Instruct
- base revision: 48d788eca847d4d7548f375ad03d3c9312f6139e
- base checkpoint SHA-256:
  36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f
- tokenizer digest:
  c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff
- FA-v1 adapter SHA-256:
  46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec

Canonical execution runtime:
- Python 3.12.3
- torch 2.7.1+cu118
- torch CUDA runtime 11.8
- cuDNN 90100
- transformers 5.16.1
- peft 0.20.0
- lm-format-enforcer 0.11.3
- tokenizers 0.23.1
- safetensors 0.8.0
- accelerate 1.14.0
- GPU: NVIDIA A40
- compute capability: 8.6
- dtype: BF16

The previously identified repository-lock drift, where a fresh uv sync resolved
torch 2.13.0+cu130 rather than the canonical torch 2.7.1+cu118 runtime, must be
closed or explicitly bound by a reproducible P0 environment specification
before P0 execution.

## 4. Interface

P0 uses the already admitted WORLD-v0 I3 interface:

- I3_CONDITIONAL_TYPED_CODEC
- neutral suffix:
  `\nAction selection JSON:\n`
- action-conditional typed JSON schema
- lm-format-enforcer syntax/type constraint
- no chat template
- no hidden behavioral directive
- no min_new_tokens workaround
- no EOS suppression
- no retry
- no fallback
- no repair

Introducing a proposal-pointer interface, repaired selector interface, or any
new semantic prompt constitutes a separately versioned study and is forbidden
inside P0 V1.

## 5. Cohort

Founders:
- A
- B
- C

Initial conditions:
- tick: 0
- state_version: 0
- lifespan_ticks: 100
- maturity_delay_ticks: 0
- refractory_interval_ticks: 0
- population_capacity: None
- resources: absent
- initial messages: none
- initial proposals: none
- initial social metadata: none

Pilot horizon:
- 12 committed ticks

Expected cognition opportunities if all founders remain alive:
- 3 agents × 12 ticks = 36 opportunities per replica

No minimum number of SEND, PROPOSE, ACCEPT, REJECT, births, messages, or other
non-WAIT actions is required.

## 6. Replicas

Two replicas use identical scientific inputs and differ only in model
completion order supplied to the cognition pipeline.

### P0-FWD

Completion order:
- A
- B
- C

### P0-REV

Completion order:
- C
- B
- A

The completion-order treatment is an infrastructure invariance test, not an
agent-visible intervention.

Neither completion order may enter model-facing ContextPack content.

## 7. Persistence

Each replica uses an independent:

- SQLiteReferenceStore
- SQLite durable commit chain
- filesystem CAS

The same store's artifact_store is shared by:

- ContextCognitionPipeline
- LiveCandidateRuntime
- durable commit provenance

Every committed cognition artifact reference must resolve durably.

## 8. Required execution path

For each tick:

1. read immutable S_t;
2. enumerate cognition opportunities;
3. compile all ContextPacks before any cognition execution;
4. execute FA-v1 cognition through LiveCandidateRuntime;
5. use I3 typed constraint;
6. bind valid candidates to ActionIntent externally;
7. retain typed rejection for invalid model output;
8. validate intents with deterministic world law;
9. deterministically plan transition fragments;
10. perform one canonical durable commit;
11. advance to S_(t+1);
12. retain ContextPack, raw-generation, cognition-evidence, event, and commit provenance.

No model call may directly mutate canonical state.

## 9. Primary P0 validity criteria

P0 V1 passes only if all applicable criteria below pass.

### P0-G1 — Infrastructure integrity

For both replicas:

- zero model-loader infrastructure failures;
- zero unexpected runtime exceptions;
- all expected tick commits complete;
- final tick = 12;
- final state_version = 12.

### P0-G2 — Evidence durability

For every cognition attempt:

- ContextPack artifact resolves;
- raw generation artifact resolves;
- cognition evidence artifact resolves;
- artifact digest verifies;
- rejected outputs remain explicit typed rejections.

No rejected output may be silently replaced by WAIT.

### P0-G3 — Replay integrity

For each replica:

- replay invokes no model inference;
- commit sequence is contiguous;
- previous/resulting state hashes verify;
- event history is append-only;
- replay final state hash equals live final state hash exactly;
- replay final snapshot equals the committed final boundary.

### P0-G4 — Completion-order invariance

Comparing P0-FWD and P0-REV:

- canonical state hash after every corresponding tick is identical;
- canonical event sequence after every corresponding tick is identical;
- validated intent projection is identical;
- transition-fragment projection is identical;
- final canonical state hash is identical.

### P0-G5 — Context identity invariance

For each `(tick, agent_id)` pair across FWD and REV:

- ContextPack context hash is identical;
- rendered model input bytes are identical;
- ContextPack identity is identical.

Completion order must not alter model-visible information.

### P0-G6 — Deterministic cognition equivalence

For each corresponding `(tick, agent_id)` pair across FWD and REV:

- generation identity is identical;
- raw model text is identical;
- token IDs are identical;
- finish reason is identical;
- raw-generation CAS digest is identical.

This criterion applies because P0 V1 uses deterministic greedy generation with
identical scientific inputs.

### P0-G7 — Visibility and privacy isolation

For every ContextPack:

- no global Snapshot dump enters model input;
- no hidden lifespan/horizon/state-version/model-revision/generation-seed field
  enters model-facing text unless already explicitly admitted by the frozen
  context contract;
- agent-visible messages and proposal records must satisfy the existing
  visibility policy;
- same-tick committed consequences cannot appear in same-tick cognition;
- another agent's private/non-projected history cannot enter the model input.

A privacy/visibility violation is a P0 failure even if final state hashes match.

## 10. Descriptive outputs that are NOT gates

The following are recorded but cannot determine P0 PASS/FAIL:

- action distribution;
- WAIT / NO_DIRECTED_ACTION frequency;
- SEND frequency;
- PROPOSE frequency;
- ACCEPT frequency;
- REJECT frequency;
- births;
- deaths;
- message count;
- proposal count;
- apparent social patterns.

No post-hoc minimum-activity criterion may be added.

## 11. Interpretation boundaries

A P0 PASS establishes only that the bounded real-model WORLD path can operate
with the tested causal, persistence, replay, privacy, and completion-order
integrity guarantees.

A P0 PASS does NOT establish:

- context-sensitive nontrivial policy competence;
- social intelligence;
- emergent cooperation;
- reproductive competence;
- stable social structure;
- language evolution;
- civilization formation;
- Founder Freeze.

Founder Freeze remains NOT_ESTABLISHED unless separately admitted.

## 12. Failure handling

If P0 fails:

- preserve raw evidence;
- classify the failure before any repair;
- do not retry the failed primary observation as a replacement;
- do not modify thresholds after observing results;
- fix implementation defects only in a separately versioned rerun;
- interface-semantic changes require a separately preregistered P0 V2 or
  appropriate admission study.

## 13. Pre-execution gate

P0 execution is forbidden until:

1. this preregistration is committed;
2. the canonical FA-v1 runtime identity is statically verified;
3. the canonical torch/CUDA environment drift is closed or reproducibly bound;
4. the P0 runner's tests pass;
5. the runner's static configuration is inspected before first execution.

