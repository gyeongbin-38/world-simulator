# WORLD P1C Foundation–Policy Phase Ablation V1

Status: PRE-EXECUTION PREREGISTRATION — FROZEN BEFORE P1C MODEL INFERENCE

## 1. Purpose

P1B established two simultaneous effects of FA-v1 on held-out R3 contexts:

- the adapter increased the global `NO_DIRECTED_ACTION` (WAIT) margin relative to the exact base model in all 160/160 held-out contexts; and
- the adapter strengthened all three preregistered action-structure contrasts relative to the exact base model, while canonical label-only selection remained WAIT-dominant.

P1C tests whether these two effects arise primarily during **WORLD-context encoding/prefill**, during **action-selection decoding/scoring**, or both.

The central mechanistic question is:

> Can FA-v1's context-structural signal survive in cached context representations when the adapter is disabled for the subsequent action-selection prefix and action-label tokens, while avoiding the full FA-v1 WAIT-margin amplification observed in P1B?

P1C is a researcher-side mechanistic ablation. It is not a behavioral admission study and cannot establish Founder Freeze.

## 2. Frozen prior evidence

Known before P1C and excluded from all P1C denominators:

- A0: I3 motor/interface admission passed; context-sensitive autonomous policy competence not established.
- P0: infrastructure/causal/persistence/replay/privacy/completion-order integrity passed; all cognition attempts WAIT.
- P1: `P1-G0 PASS`, `P1-G1 FAIL`, `P1-G2 FAIL`.
- P1 post-hoc latent-margin V1: complete five-label ranking unchanged, with sub-rank score movement.
- P1B: `G0 PASS`, `G1 PASS`, `G2 PASS`, `G3 FAIL`, `G4 PASS`, `G5 BASE_ONLY FAIL`, `G5 FA_V1 FAIL`.
- P1B held-out label-only selection: BASE_ONLY was predominantly `DIRECT_TEXT`; FA_V1 was `NO_DIRECTED_ACTION` in all 160 contexts.
- P1B WAIT-margin adapter effect: positive in 160/160 held-out contexts, median +3.52783203125 total-log-probability units.
- P1B adapter structural gains: `S_msg` PASS, `S_prop` PASS, `S_owner` PASS.

P1C does not reinterpret or alter those results.

## 3. Scientific boundary

P1C preserves the WORLD experimental boundary:

- no social role, trust score, cooperation reward, desirability score, emotion, personality, rank, or mate preference;
- no action recommendation is inserted into model-visible context;
- no weight update;
- no simulation-state commit;
- no retry, fallback, repair, EOS suppression, minimum-token workaround, or chat template;
- no residual WAIT subtraction or hand calibration is fed to the model;
- all phase switching is researcher-side runtime control;
- all measured action labels remain diagnostic and are never executed.

## 4. Frozen deployment identities

Base model:

- repository: `allenai/OLMo-2-0425-1B-Instruct`
- revision: `48d788eca847d4d7548f375ad03d3c9312f6139e`
- checkpoint SHA-256: `36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f`
- tokenizer digest: `c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff`
- tokenizer BOS/EOS: 100257
- tokenizer PAD: 100277

FA-v1:

- adapter artifact: `F0_FA_V1_FORMAL`
- adapter SHA-256: `46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec`
- adapter config SHA-256: `687100a0b6340b6096ca1e86066d3c13224b3c8e14ce9fb1b0cf78a52a8bdb7d`
- target modules: q/k/v/o attention projections only

Runtime:

- Python 3.12.3
- torch 2.7.1+cu118
- transformers 5.16.1
- peft 0.20.0
- BF16
- NVIDIA A40
- canonical pip-freeze SHA-256: `a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf`

No parameter may be updated.

## 5. Held-out cohort

P1C uses new deterministic R3 fixture cases not used by P1 or P1B:

- case indices: 2000–2031 inclusive
- 32 matched case sets
- context classes:
  - `QUIET`
  - `MESSAGE_RECEIVED`
  - `PROPOSAL_RECEIVED`
  - `OWN_PROPOSAL_PENDING`
  - `RECENT_INTERACTION`
- total canonical contexts: 160

The 32 deterministic variants are robustness fixtures, not IID population samples.

## 6. Phase boundary

For every context, the model-visible sequence is split at one frozen byte/token boundary.

### Phase A — WORLD context prefill

Contains exactly the canonical rendered R3 WORLD context bytes and nothing from the researcher scoring scaffold.

### Phase B — selector/scoring continuation

Begins with the exact P1/P1B teacher-forced diagnostic prefix:

`\nAction selection JSON:\n{"action_label":"`

and continues with one candidate action label token sequence.

The adapter state may differ between Phase A and Phase B according to the condition below. The Phase A `past_key_values` cache must be reused without recomputing the WORLD context after the phase switch.

The boundary is architectural: FA-v1 may affect cached WORLD-context representations in Phase A, but under a BASE Phase B it must not execute on the action-selection prefix or candidate-label tokens.

## 7. Four frozen phase conditions

All four conditions receive byte-identical canonical WORLD context and score the same five action labels.

### C00 — BASE→BASE

- Phase A: adapter disabled
- Phase B: adapter disabled

This is the exact-base phase-switch control.

### C11 — FA→FA

- Phase A: FA-v1 enabled
- Phase B: FA-v1 enabled

This is the full-adapter control and should reproduce the direction of P1B effects on the new cohort.

### C10 — FA→BASE

- Phase A: FA-v1 enabled
- Phase B: adapter disabled

This is the candidate foundation/policy decoupling condition. It tests whether FA-v1 context structure remains useful through cached context representations when the selector/scoring continuation is base-only.

### C01 — BASE→FA

- Phase A: adapter disabled
- Phase B: FA-v1 enabled

This isolates selector/scoring-side adapter effects when the WORLD context itself was encoded without FA-v1.

No other phase pattern is allowed.

## 8. Base-wrapper equivalence control

Phase switching must be implemented through the exact PEFT-wrapped FA-v1 runtime so one cached prefill can be followed by a different adapter state.

Because `adapter disabled` inside a PEFT wrapper is an implementation mechanism, not automatically identical to a separately loaded exact base model, P1C includes a mandatory control:

- separately load the exact BASE_ONLY runtime used by the established deployment path;
- on all 160 held-out contexts, compute the ordinary non-phase-switched BASE_ONLY five-label teacher-forced scores;
- compare them with C00 scores from the phase-switch runtime;
- action-label token IDs must be identical;
- for every label/context, absolute total-log-probability difference must be <= `1e-5` and absolute mean-log-probability difference must be <= `1e-5`.

If this equivalence control fails, all phase-attribution gates are `NOT_EVALUABLE`.

## 9. Frozen teacher-forced action-label scoring

Five canonical labels:

- `NO_DIRECTED_ACTION`
- `DIRECT_TEXT`
- `OPEN_BILATERAL_REQUEST`
- `CONFIRM_BILATERAL_REQUEST`
- `DECLINE_BILATERAL_REQUEST`

For every condition/context/label, record:

- token IDs;
- total sequence log probability;
- mean log probability per label token;
- complete rank ordering.

Primary scoring metric is total sequence log probability, matching P1/P1B. Mean-token score is secondary descriptive evidence only.

## 10. Frozen score definitions

Let `L_x(a,c,i)` be total log probability for action label `a`, context `c`, case `i`, and phase condition `x` in `{C00,C11,C10,C01}`.

Let `W = NO_DIRECTED_ACTION`, and let `D` be the four directed actions.

### 10.1 WAIT margin

`M_x(c,i) = L_x(W,c,i) - max_{a in D} L_x(a,c,i)`

### 10.2 Directed-relative score

`r_x(a,c,i) = L_x(a,c,i) - L_x(W,c,i)`

### 10.3 Within-directed centered score

`q_x(a,c,i) = r_x(a,c,i) - mean_{d in D} r_x(d,c,i)`

### 10.4 Structural contrasts

Using the same P1B definitions:

- `S_msg_x(i)` measures `DIRECT_TEXT` specificity for `MESSAGE_RECEIVED` versus `QUIET` after within-directed centering.
- `S_prop_x(i)` measures proposal-response-family specificity for `PROPOSAL_RECEIVED` versus `QUIET`.
- `S_owner_x(i)` measures proposal-response-family separation between `PROPOSAL_RECEIVED` and `OWN_PROPOSAL_PENDING`.

The exact formulae and label families must be identical to P1B; no new structural metric may replace them after execution.

## 11. P1C-G0 integrity gate

P1C mechanistic interpretation is valid only if all are true:

- exact static deployment identity passes;
- canonical runtime freeze matches exactly;
- 160/160 held-out contexts compile;
- WORLD context bytes are identical across C00/C11/C10/C01;
- phase boundary tokenization is deterministic and identical across conditions;
- C00 separate-base equivalence control passes all labels/contexts at tolerance <= `1e-5`;
- 160 score sets complete for each of C00/C11/C10/C01;
- every score set contains exactly the five frozen labels;
- Phase A cache is reused without WORLD-context recomputation after switching adapter state;
- runtime logs prove the intended adapter state for each phase;
- exact repeat of the first score set in every phase condition is equal under the frozen numeric equality rule;
- no model weight updates;
- no simulation state commits;
- evidence is digest-addressed and immutable.

If G0 fails, G1–G5 are `NOT_EVALUABLE`.

## 12. P1C-G1 decode-side WAIT induction

This tests whether enabling FA-v1 only for selector/scoring continuation is sufficient to increase WAIT margin relative to exact-base phase behavior.

For all 160 matched contexts:

`D_decode(c,i) = M_C01(c,i) - M_C00(c,i)`

G1 passes if:

- median `D_decode > 0`; and
- at least 75% of the 160 values are > 0.

PASS interpretation:

> FA-v1 activation during selector/scoring continuation is sufficient to consistently increase WAIT margin even when the WORLD context was encoded by the base model.

## 13. P1C-G2 prefill-side WAIT induction

For all 160 matched contexts:

`D_prefill(c,i) = M_C10(c,i) - M_C00(c,i)`

G2 passes if:

- median `D_prefill > 0`; and
- at least 75% of values are > 0.

PASS means FA-v1 context encoding alone is sufficient to carry a persistent WAIT-margin increase into base-only selector scoring.

FAIL does not imply the prefill is behaviorally neutral; it means consistent WAIT-margin induction is not established under this phase isolation.

## 14. P1C-G3 structural carryover through FA→BASE

For each structural contrast `S in {S_msg,S_prop,S_owner}` define:

`A_prefill_S(i) = S_C10(i) - S_C00(i)`

A contrast has `PREFILL_STRUCTURAL_GAIN` if:

- median `A_prefill_S > 0`; and
- at least 75% of 32 values are > 0.

G3 passes if at least 2 of 3 structural contrasts have `PREFILL_STRUCTURAL_GAIN`.

PASS interpretation:

> FA-v1 adds context/action structural information during WORLD-context prefill that remains measurable when action-selection scoring is subsequently base-only.

This is not autonomous policy competence.

## 15. P1C-G4 decoupling candidate gate

G4 tests the specific architectural hypothesis motivating P1C.

Define full-adapter versus decoupled WAIT reduction:

`R_wait(c,i) = M_C11(c,i) - M_C10(c,i)`

The FA→BASE decoupling condition is a `DECOUPLING_CANDIDATE` only if all are true:

1. G3 passes;
2. median `R_wait > 0`;
3. at least 75% of the 160 `R_wait` values are > 0.

PASS interpretation is limited to:

> On the tested teacher-forced interface, FA→BASE preserves preregistered adapter-derived structural gain while reducing the WAIT margin relative to FA→FA. This supports a separately versioned runtime architecture experiment.

G4 does not authorize deployment or establish behavior.

## 16. P1C-G5 latent rank-1 context sensitivity

For each phase condition separately, take the teacher-forced rank-1 action label in each of the 160 contexts and compute the same matched sensitivity structure used by P1/P1B:

- matched case is sensitive if its five context labels are not all identical;
- matched sensitivity rate over 32 case sets;
- TVD of each non-QUIET context-class rank-1 distribution versus QUIET.

A condition passes latent rank-1 context sensitivity if:

- matched sensitivity rate >= 0.25; and
- at least 2 of 4 non-QUIET classes have TVD >= 0.25.

Report G5 separately for C00/C11/C10/C01.

No particular action label is required. G5 remains diagnostic and is not WORLD behavioral admission.

## 17. Frozen interpretation matrix

Provided G0 passes:

### G1 PASS, G2 FAIL

WAIT amplification is primarily attributable to adapter activity during selector/scoring continuation under this phase decomposition.

### G1 FAIL, G2 PASS

WAIT amplification persists from FA-v1 WORLD-context encoding even when later action scoring is base-only.

### G1 PASS, G2 PASS

Both context-prefill and selector/scoring phases contribute to WAIT amplification.

### G1 FAIL, G2 FAIL

Neither isolated phase is sufficient by itself; the P1B full-adapter effect may require cross-phase interaction.

### G3 PASS, G4 PASS

FA-derived structural signal survives through cached WORLD-context representations and the FA→BASE condition reduces full-adapter WAIT bias. This is the strongest preregistered evidence for a future foundation/policy phase-decoupled runtime experiment.

### G3 PASS, G4 FAIL

Structural carryover exists, but the proposed phase decoupling does not consistently reduce WAIT margin relative to FA→FA.

### G3 FAIL

The tested FA structural gain does not reliably survive when the adapter is disabled for the scoring continuation. The P1B structural improvement may depend on adapter activity during scoring rather than a reusable foundation representation.

G5 is always reported separately and cannot override G1–G4.

## 18. Explicit non-claims

P1C cannot establish:

- Founder Freeze;
- autonomous policy competence;
- behavioral validity;
- that FA→BASE should be deployed;
- that a scalar WAIT correction is legitimate;
- that the base model is an adequate selector;
- that FA-v1 is a neutral policy module.

## 19. Post-execution boundary

After the first P1C model forward pass:

- this preregistration is immutable;
- thresholds cannot change;
- phase boundary cannot change;
- no failed run may be overwritten;
- any implementation defect requires a separately versioned rerun;
- any hidden-state probing, per-layer attribution, residual logit correction, alternative selector, or generation experiment is separately versioned post-P1C work.
