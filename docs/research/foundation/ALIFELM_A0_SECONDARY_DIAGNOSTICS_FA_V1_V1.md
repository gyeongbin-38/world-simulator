# A0 Secondary Diagnostics — Exact FA-v1 V1

Status: PRE-EXECUTION FROZEN PLAN

## Trigger

A0_AUTONOMOUS_INTERFACE_ADMISSION_V1 completed with ADMISSION_PASS under I3.
The selected I3 treatment produced valid codec/domain outputs but all 80 primary
contexts selected NO_DIRECTED_ACTION / WAIT.

This document does not modify, reinterpret, or retroactively gate A0 v1.

## Scientific role

These are researcher-only secondary diagnostics permitted by the frozen A0 v1
preregistration when the primary study exposes an interface-bias mechanism.

They are diagnostic only.

They MUST NOT:
- change the A0 v1 result;
- introduce a new promotion threshold;
- introduce a new action-frequency target;
- select a new interface treatment;
- alter prompt wording, fixture semantics, selector codebooks, or scoring logic;
- update model weights;
- commit simulation state.

## Exact deployment identity

Use the same accepted WORLD v0 Foundation deployment used by A0 v1:

- base: allenai/OLMo-2-0425-1B-Instruct
- base revision: 48d788eca847d4d7548f375ad03d3c9312f6139e
- base checkpoint SHA-256:
  36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f
- tokenizer digest:
  c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff
- FA-v1 adapter SHA-256:
  46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec
- FA-v1 adapter config SHA-256:
  687100a0b6340b6096ca1e86066d3c13224b3c8e14ce9fb1b0cf78a52a8bdb7d
- runtime: NVIDIA A40, CUDA path, BF16
- no sampling for deterministic diagnostics
- no retry, fallback, repair, or chat template

The loader/profile identity MUST reuse the validated A0 exact-FA-v1 deployment
path rather than the historical Pythia profiles embedded in the original R3/R4
research tools.

## Frozen diagnostics
### D1 — I-05R3 full action-label sequence scoring

Reuse the existing:
- R3ContextClass fixtures;
- compile_r3_fixture semantics;
- ACTION_SCORE_PREFIX;
- score_action_labels implementation;
- existing action-label set and scoring arithmetic.

Purpose:
measure latent relative sequence likelihoods for the available action labels
across the five existing R3 context classes.

No PASS/FAIL threshold is defined.

### D2 — I-05R4 balanced opaque selector codebooks

Reuse the existing:
- balanced_selector_codebooks;
- selector rendering;
- selector scoring;
- selector parser;
- codebook/action mapping;
- R3 fixtures.

Purpose:
test whether the observed WAIT collapse survives balanced opaque remapping or
is associated with surface action labels / schema branch representation.
No PASS/FAIL threshold is defined.

### D3 — Existing forced grounding diagnostics

Reuse the existing R4 grounding machinery without changing schemas or handle
semantics.

Purpose:
separate action-selection effects from reference/handle grounding capacity.

No PASS/FAIL threshold is defined.

## Implementation firewall

Historical tools `tools/i05r3_model_probe.py` and
`tools/i05r4_motor_probe.py` remain unchanged because their model profiles are
historical Pythia-specific diagnostics.

A new exact-FA-v1 runner may reuse their diagnostic functions/mechanics while
replacing only the model deployment/profile/loading layer with the exact A0
OLMo-2 + FA-v1 loader.

All raw outputs and diagnostic records remain researcher evidence.

Any new prompt, treatment, threshold, scoring rule, fixture, codebook, or
behavioral criterion requires a separately versioned study and cannot be
silently introduced here.
