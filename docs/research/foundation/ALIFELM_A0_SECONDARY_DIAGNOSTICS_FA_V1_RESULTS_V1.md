# A0 Secondary Diagnostics — FA-v1 Results V1

Status: POST-EXECUTION RESULTS — INTERPRETATION FROZEN

This document records descriptive secondary-diagnostic results only.
It does not modify, reinterpret, or retroactively gate
`A0_AUTONOMOUS_INTERFACE_ADMISSION_V1`.

## Deployment identity

- Base model: `allenai/OLMo-2-0425-1B-Instruct`
- Base revision: `48d788eca847d4d7548f375ad03d3c9312f6139e`
- Base checkpoint SHA-256:
  `36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f`
- FA-v1 adapter SHA-256:
  `46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec`
- Diagnostic runner commit:
  `b61180c4a43a5003965de799b70cdd7ff9c23f3e`
- Device: NVIDIA CUDA
- dtype: BF16

## Primary A0 status

`A0_AUTONOMOUS_INTERFACE_ADMISSION_V1` remains:

- Status: `ADMISSION_PASS`
- Minimal motor treatment: `I3`
- Minimal autonomous-core treatment: `I3`
- Founder Freeze: `NOT_ESTABLISHED_BY_A0_ALONE`

Secondary diagnostics do not alter this result.

## D1 — R3 canonical action-label diagnostic

Evidence:

- summary SHA-256:
  `cc5b5aa69d2981b8ef5440b6771dd36103d3f7d9e5f982092ea9bb419e140b2f`
- stdout SHA-256:
  `02e44d89ca3069ad037c2774702f1c360eb9d3ffe094db1053f2a6d5e23e8cc8`

Across 5 R3 context classes × 10 cases:

- I3 generation selected `NO_DIRECTED_ACTION` in 50/50 cases.
- Codec validity: 50/50.
- Domain validity: 50/50.
- Commit validity: 50/50.
- `NO_DIRECTED_ACTION` ranked first under the existing teacher-forced
  full-label scoring diagnostic in 50/50 cases.

Interpretation:

The canonical action-label path exhibits a strong
`NO_DIRECTED_ACTION` conditional sequence-likelihood preference.

This does not by itself establish that the model has a semantic
or context-independent WAIT policy.

## D2 — R4 balanced opaque-selector diagnostic

Evidence:

- summary SHA-256:
  `b123a88518db616847c635e276579f96897ad5b5e8bca217d6dddf44592d6238`
- stdout SHA-256:
  `d9e273c159c5a0b935b6063f082364bbaa4d91c745c90bb57720d3ed509b21a4`

Observed generation:

- `PROPOSE`: 236/250
- `SEND`: 14/250
- other mapped actions: 0/250

Implementation-validity audit found that generated R4 objects may emit
`payload` before `selector`.

In audited examples across all five balanced codebooks, generation first
produced a PROPOSE-compatible payload signature:

`payload = {"target_agent_id": ...}`

and emitted the corresponding opaque selector afterward.

Therefore the action-conditional payload schema can reveal or determine
the action branch before the opaque selector is emitted.

Interpretation:

R4 V1 is confounded by action-conditional payload-schema leakage and
unconstrained JSON property order.

R4 V1 therefore does NOT identify semantic action preference versus
selector-token/surface preference.

The R4 evidence remains valid evidence of what the diagnostic generated;
its causal interpretation is restricted.

Any repaired selector experiment requires a separately versioned,
pre-registered diagnostic or admission study.

## D3 — forced grounding diagnostic

Evidence:

- summary SHA-256:
  `23f54c01098ea91926e6d1bcb99e7f8c50009127835de632e245b50a0ec9ed99`
- stdout SHA-256:
  `dbe67cb0b8d2780dda963d7aee6fbe543a9059c69b759089b580f0e0025b7e86`

Cases per action/mode: 10.

### Peer-reference actions

For `SEND` and `PROPOSE`:

- G0: visible-reference hit 20/20; domain valid 20/20; commit valid 20/20.
- G1_FREE: visible-reference hit 20/20; domain valid 20/20; commit valid 20/20.
- G1_POINTER: visible-reference hit 20/20; domain valid 20/20; commit valid 20/20.

Peer grounding is operationally strong in these diagnostics.

### Proposal-reference actions

For `ACCEPT` and `REJECT`:

G0:
- codec valid: 20/20
- visible proposal-reference hit: 0/20
- domain valid: 0/20
- commit valid: 0/20
- hallucinated/non-visible proposal reference: 20/20

G1_FREE:
- codec valid: 20/20
- visible proposal-reference hit: 0/20
- domain valid: 0/20
- commit valid: 0/20
- hallucinated/non-visible proposal reference: 20/20

Observed free references were dominated by values such as
`no_label` and `noproposal`.

G1_POINTER:
- codec valid: 20/20
- visible proposal-reference hit: 20/20
- domain valid: 20/20
- commit valid: 20/20
- hallucinated reference: 0/20
- generated reference `R0`: 20/20

Interpretation:

FA-v1 can ground peer references reliably under the tested interface.

FA-v1 does not reliably copy or select visible proposal identifiers under
the tested free-reference interfaces.

A deterministic local proposal-pointer interface resolves the tested
grounding failure, but introducing such an interface into autonomous
WORLD execution would constitute a separately versioned interface change.

## Frozen scientific interpretation

1. A0 v1 remains a formal PASS under its preregistered validity criteria.
2. Motor/interface validity under I3 is established.
3. Context-sensitive nontrivial autonomous policy competence is not yet established.
4. Canonical action-label scoring shows a strong `NO_DIRECTED_ACTION`
   conditional preference.
5. R4 V1 cannot distinguish semantic action preference from interface
   effects because of payload-schema branch leakage.
6. Peer-reference grounding is strong in D3.
7. Free proposal-ID grounding is weak in D3.
8. Pointer-constrained proposal grounding succeeds in D3.
9. Founder Freeze remains NOT_ESTABLISHED.
10. No secondary diagnostic result retroactively changes A0 v1.

## Next research-quality gates

No additional post-hoc diagnostic treatment is introduced here.

Next gates are:

1. archive and independently verify diagnostic evidence;
2. clean-room reproducibility from a fresh environment;
3. bounded multi-agent WORLD end-to-end pilot;
4. replay/state/event integrity audit;
5. privacy and causal-isolation audit;
6. separately preregister any A0 v2 interface change before execution.
