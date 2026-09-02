# WORLD P0 End-to-End Multi-Agent Pilot — Results V1

Status: POST-EXECUTION RESULTS — PRIMARY P0 GATES PASS; PRE-EXECUTION TEST RECORD DEVIATION NOTED

## 1. Scope

This document freezes the observed results of `WORLD_P0_END_TO_END_PILOT_V1`.

The preregistered purpose of P0 was infrastructure and causal-integrity validation of the accepted WORLD-v0 real-model path. P0 was not an admission test for nontrivial social or autonomous policy competence, and action frequency was explicitly non-gating.

## 2. Frozen execution identity

- preregistration: `docs/research/world/WORLD_P0_END_TO_END_PILOT_V1.md`
- preregistration commit: `5ba7affcfaf0905a48a1010b4220d9cbbe00387a`
- runtime-environment freeze commit: `3fd2145c06a8c9503a7ae674de78b6c2a93cf1c7`
- primary execution runner commit: `cc5c2bbb0d1890962f919417d157aa1aae43bf69`
- runner config SHA-256: `2e5561690462bcc14ebde2d8a82d4f670c5cc1a438447c41fd662ff191b05ed2`
- canonical runtime pip-freeze SHA-256: `a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf`
- base checkpoint SHA-256: `36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f`
- base revision: `48d788eca847d4d7548f375ad03d3c9312f6139e`
- FA-v1 adapter SHA-256: `46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec`
- tokenizer aggregate SHA-256: `c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff`
- interface: `I3_CONDITIONAL_TYPED_CODEC`
- generation: deterministic greedy, max_new_tokens=128, seed=35020260831
- execution hardware: NVIDIA A40, BF16, compute capability 8.6

## 3. Pre-execution checks actually observed

Before primary generation, the following checks were observed on the execution host:

- runner Python compilation: PASS (`P0_CC5C2BB_SYNTAX_OK`)
- runner CLI import/argument construction: PASS
- exact runner commit check: PASS
- exact config SHA-256 check: PASS
- static deployment identity: PASS
- canonical runtime environment checks: PASS
  - Python 3.12.3
  - torch 2.7.1+cu118
  - CUDA runtime 11.8
  - cuDNN 90100
  - NVIDIA A40
  - compute capability 8.6
  - package count 60
  - exact pip-freeze SHA-256 match

### 3.1 Recorded process deviation

The preregistration stated that execution was forbidden until "the P0 runner's tests pass." A distinct P0-specific pytest result was not recorded before the primary execution. The pre-execution record contains syntax compilation, CLI import, and full static validation, but not a separately identified P0-runner pytest invocation.

This is recorded as a process/provenance deviation. It does not alter the observed G1-G7 measurements and must not be silently relabeled as if a dedicated pre-execution pytest result existed. Any later test run is post-execution characterization and cannot retroactively erase this timing distinction.

## 4. Primary result

Observed primary status emitted by the runner:

`PASS`

All preregistered primary measurement gates G1-G7 passed in the produced evidence.

### 4.1 P0-FWD

- P0-G1: PASS
- P0-G2: PASS
- P0-G3: PASS
- P0-G7: PASS
- model inference calls: 36
- cognition opportunities: 36
- replay model-call delta: 0
- action distribution: WAIT = 36
- final tick: 12
- final state_version: 12
- final state hash: `83f8a17a150fb09b25ba6e7fce5635212d979d14673a84d48cefa0f9ca08fb19`
- final agents: 3
- final messages: 0
- final proposals: 0
- final events: 0

### 4.2 P0-REV

- P0-G1: PASS
- P0-G2: PASS
- P0-G3: PASS
- P0-G7: PASS
- model inference calls: 36
- cognition opportunities: 36
- replay model-call delta: 0
- action distribution: WAIT = 36
- final tick: 12
- final state_version: 12
- final state hash: `83f8a17a150fb09b25ba6e7fce5635212d979d14673a84d48cefa0f9ca08fb19`
- final agents: 3
- final messages: 0
- final proposals: 0
- final events: 0

### 4.3 Cross-replica invariance

- P0-G4: PASS
- P0-G5: PASS
- P0-G6: PASS
- mismatch count: 0

The FWD and REV replicas were identical under the frozen comparison projections for canonical state/events/validated intents/fragments, model-facing context identity, and deterministic generation evidence.

## 5. Descriptive behavior

Across both replicas:

- total cognition opportunities: 72
- total model inference calls: 72
- WAIT: 72 / 72 = 100%
- SEND: 0
- PROPOSE: 0
- ACCEPT: 0
- REJECT: 0
- births: 0
- messages committed: 0
- proposals committed: 0
- domain events committed: 0

This all-WAIT result is descriptive only. The preregistration explicitly stated that a WAIT-only trajectory may pass P0 and prohibited adding a post-hoc activity threshold.

## 6. Canonical evidence archive

Canonical archive:

`WORLD_P0_END_TO_END_PILOT_V1_CC5C2BB_CANONICAL.tar.gz`

SHA-256:

`c40cee4041dd2d32a40e4257bc7c890e9cbbc5ef3c42b8f7ec68b6a477578d0a`

Archive verification was performed by extracting to an independent verification directory and recursively comparing the extracted evidence directory against the source evidence directory with `diff -qr`. The comparison emitted no differences and the verification marker was:

`P0_CANONICAL_ARCHIVE_VERIFIED`

## 7. Interpretation

The primary P0 measurements support the following bounded conclusion:

> The tested real-model WORLD path completed the bounded multi-agent pilot with the preregistered causal, persistence, replay, privacy, context-identity, and completion-order invariance measurements passing under the exact frozen execution configuration.

P0 does **not** establish:

- context-sensitive nontrivial autonomous policy competence;
- social intelligence;
- emergent cooperation;
- reproductive competence;
- stable social structure;
- language evolution;
- civilization formation;
- Founder Freeze.

The observed 72/72 WAIT behavior is consistent with the prior concern that motor/interface validity does not itself establish nontrivial context-sensitive autonomous policy competence.

Founder Freeze remains:

`NOT_ESTABLISHED`

## 8. Frozen classification

- Primary G1-G7 measurement result: `PASS`
- Canonical evidence archive: `VERIFIED`
- Completion-order invariance: `PASS`
- Replay without inference: `PASS`
- Nontrivial policy competence: `NOT_ESTABLISHED`
- Founder Freeze: `NOT_ESTABLISHED`
- Pre-execution dedicated runner-test record: `NOT_ESTABLISHED / PROCESS DEVIATION RECORDED`

No later result may erase or relabel the pre-execution timing distinction in Section 3.1. A later runner-test execution may be appended only as post-execution characterization or used in a separately versioned rerun.
