# WORLD P1C-v2 Common-Topology Foundation–Policy Phase Ablation V1

Status: PRE-EXECUTION PREREGISTRATION — FROZEN BEFORE P1C-v2 MODEL INFERENCE

Study ID: `WORLD_P1C_V2_COMMON_TOPOLOGY_PHASE_ABLATION_V1`

## 1. Purpose

P1C-v1 terminated at its integrity gate because ordinary full-sequence BASE scoring and cached split-prefill C00 scoring were not numerically equivalent in BF16. P1C-v1 therefore remains `P1C_BASE_WRAPPER_EQUIVALENCE_FAIL`; its phase-attribution gates were never evaluated.

The separately frozen D1 diagnostic exactly reconstructed that discrepancy and localized it to the BF16 full-versus-cached execution topology:

- P1C-v1 max absolute total-logP discrepancy: `0.21875`;
- D1 bare BASE full-versus-cached BF16 max absolute total-logP discrepancy: `0.21875`;
- P1C-v1 max absolute mean-logP discrepancy: `0.0703125`;
- D1 bare BASE full-versus-cached BF16 max absolute mean-logP discrepancy: `0.0703125`;
- PEFT-disabled wrapper contribution under full scoring: exactly `0.0` across 800 comparisons;
- PEFT-disabled wrapper contribution under cached scoring: exactly `0.0` across 800 comparisons;
- FP32 sharply attenuated, but did not mathematically eliminate, the full-versus-cached discrepancy.

P1C-v2 therefore does not compare a full-sequence path to a cached path. All causal phase conditions use the same cached split-prefill scoring topology. The scientific question remains:

> Does FA-v1 encode context/action structural information during WORLD-context prefill that remains measurable when FA-v1 is disabled for selector/scoring continuation, and does that FA→BASE condition reduce the WAIT-margin amplification observed when FA-v1 remains enabled through scoring?

P1C-v2 is a mechanistic study only. It cannot establish autonomous policy competence, behavioral admission, deployment suitability, or Founder Freeze.

## 2. Frozen prior evidence

Known before P1C-v2 and excluded from all P1C-v2 denominators:

- A0: I3 motor/interface admission passed; context-sensitive autonomous policy competence not established.
- P0: infrastructure/causal/persistence/replay/privacy/order integrity established; all cognition attempts WAIT.
- P1: no generated or latent rank-1 context-sensitive policy evidence.
- P1 post-hoc: rank-stable but score-sensitive WAIT dominance.
- P1B: FA-v1 increased WAIT margin in 160/160 held-out contexts and improved all three adapter structural-gain contrasts relative to BASE, while absolute structural presence passed only ownership.
- P1C-v1: integrity failed before phase attribution because full BASE and cached C00 BF16 scores were not equivalent.
- P1C-D1: the P1C-v1 discrepancy was exactly reconstructed by bare BASE full-versus-cached BF16 scoring; disabled PEFT wrapping contributed zero measurable difference in the tested full and cached controls.

P1C-v2 does not reopen, repair, or retroactively pass P1C-v1.

## 3. Scientific boundary

P1C-v2 preserves the WORLD experimental boundary:

- no predefined friendship, hostility, leadership, team, profession, family role, trust score, cooperation reward, desirability score, emotion, personality, social rank, or mate preference;
- no action recommendation is inserted into model-visible context;
- no model weight update;
- no simulation-state commit;
- no retry, fallback, repair, EOS suppression, minimum-token workaround, or chat template;
- no residual WAIT subtraction, scalar correction, logit calibration, or hand-tuned action threshold;
- all phase switching is researcher-side runtime control;
- measured action labels are diagnostic only and are never committed as simulation actions.

## 4. Frozen deployment identities

Base model:

- repository: `allenai/OLMo-2-0425-1B-Instruct`
- revision: `48d788eca847d4d7548f375ad03d3c9312f6139e`
- checkpoint SHA-256: `36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f`
- tokenizer digest: `c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff`
- BOS/EOS token ID: `100257`
- PAD token ID: `100277`

FA-v1:

- artifact: `F0_FA_V1_FORMAL`
- adapter SHA-256: `46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec`
- adapter config SHA-256: `687100a0b6340b6096ca1e86066d3c13224b3c8e14ce9fb1b0cf78a52a8bdb7d`
- target modules: attention q/k/v/o projections only

Runtime:

- Python 3.12.3
- torch 2.7.1+cu118
- transformers 5.16.1
- peft 0.20.0
- canonical inference dtype: BF16
- NVIDIA A40
- canonical pip-freeze SHA-256: `a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf`
- runtime package count: 60

No parameter may be updated.

## 5. Fresh held-out cohort

P1C-v2 uses deterministic R3 fixtures not used in P1, P1B, P1C-v1, or D1 primary measurements:

- case indices: `3000..3031` inclusive;
- 32 matched case sets;
- context classes in frozen order:
  1. `QUIET`
  2. `MESSAGE_RECEIVED`
  3. `PROPOSAL_RECEIVED`
  4. `OWN_PROPOSAL_PENDING`
  5. `RECENT_INTERACTION`
- total canonical WORLD contexts: 160.

These deterministic variants are robustness fixtures, not IID population samples. No p-values are used.

## 6. Common cached execution topology

Every primary condition uses the same scorer implementation and the same split boundary.

### Phase A — WORLD context prefill

Contains exactly the canonical rendered R3 WORLD-context bytes and nothing from the researcher scoring scaffold.

### Phase B — selector/scoring continuation

Begins with exactly:

`\nAction selection JSON:\n{"action_label":"`

and continues with one frozen candidate action-label token sequence.

For each condition:

1. Phase A is executed exactly once under the condition's Phase-A adapter state;
2. the resulting `past_key_values` cache is reused;
3. Phase B selector prefix is executed under the condition's Phase-B adapter state without recomputing WORLD context;
4. candidate-label scoring reuses cloned cache state so one candidate cannot contaminate another;
5. attention-mask/cache semantics are identical across all four conditions.

No primary P1C-v2 condition uses ordinary full-sequence scoring.

This is an operational phase decomposition. LoRA-modified K/V values can be directly cached, while Q/O effects may influence later hidden states and therefore later cached values. P1C-v2 does not claim pure per-module localization.

## 7. Four frozen phase conditions

All conditions use one exact PEFT-wrapped FA-v1 runtime and differ only in adapter state by phase.

### C00 — BASE→BASE

- Phase A: adapter disabled
- Phase B: adapter disabled

### C11 — FA→FA

- Phase A: FA-v1 enabled
- Phase B: FA-v1 enabled

### C10 — FA→BASE

- Phase A: FA-v1 enabled
- Phase B: adapter disabled

This is the candidate foundation/policy decoupling condition.

### C01 — BASE→FA

- Phase A: adapter disabled
- Phase B: FA-v1 enabled

No other phase pattern is allowed.

## 8. Cached-wrapper parity control

D1 found exact zero difference between separately loaded bare BASE cached scoring and PEFT-disabled cached scoring across all 800 tested label comparisons. P1C-v2 repeats this control on the fresh cohort under the same common cached topology.

Separately load the exact bare BASE BF16 runtime and compute cached split-prefill five-label scores on all 160 P1C-v2 contexts using the exact same phase boundary and cached scorer topology.

Compare bare cached BASE against C00:

- rendered WORLD bytes must be identical;
- context, prefix, and candidate token IDs must be identical;
- every total log probability must be exactly equal under serialized numeric equality;
- every mean log probability must be exactly equal;
- every full rank must be identical.

This is not a replacement for P1C-v1's failed full-versus-cached equivalence test. It is a same-topology implementation control supported by D1.

If cached-wrapper parity fails, P1C-v2 phase attribution is `NOT_EVALUABLE`.

## 9. Frozen action-label scorer

Use exactly five labels in frozen order:

1. `NO_DIRECTED_ACTION`
2. `DIRECT_TEXT`
3. `OPEN_BILATERAL_REQUEST`
4. `CONFIRM_BILATERAL_REQUEST`
5. `DECLINE_BILATERAL_REQUEST`

For every condition/context/label record:

- context token IDs;
- selector-prefix token IDs;
- candidate-label token IDs;
- total sequence log probability;
- mean log probability;
- complete five-label rank.

Primary metric is total sequence log probability. Mean-token score is secondary descriptive evidence only.

## 10. Frozen score definitions

Let `L_x(a,c,i)` be total log probability for action label `a`, context class `c`, case `i`, and condition `x ∈ {C00,C11,C10,C01}`.

Let `W = NO_DIRECTED_ACTION`; let `D` be the four directed actions.

WAIT margin:

`M_x(c,i) = L_x(W,c,i) - max_{a∈D} L_x(a,c,i)`

Directed-relative score:

`r_x(a,c,i) = L_x(a,c,i) - L_x(W,c,i)`

Within-directed centered score:

`q_x(a,c,i) = r_x(a,c,i) - mean_{d∈D} r_x(d,c,i)`

Structural contrasts use exactly the P1B definitions:

- `S_msg_x(i) = q_x(DIRECT_TEXT, MESSAGE_RECEIVED, i) - q_x(DIRECT_TEXT, QUIET, i)`;
- response family `R = {CONFIRM_BILATERAL_REQUEST, DECLINE_BILATERAL_REQUEST}`;
- other directed family `O = {DIRECT_TEXT, OPEN_BILATERAL_REQUEST}`;
- `F_x(c,i) = mean_{a∈R} q_x(a,c,i) - mean_{a∈O} q_x(a,c,i)`;
- `S_prop_x(i) = F_x(PROPOSAL_RECEIVED,i) - F_x(QUIET,i)`;
- `S_owner_x(i) = F_x(PROPOSAL_RECEIVED,i) - F_x(OWN_PROPOSAL_PENDING,i)`.

No alternate structural metric may replace these after execution.

## 11. P1C-v2 G0 — integrity

G0 passes only if all are true:

- exact frozen model/tokenizer/adapter/runtime identities pass;
- canonical runtime freeze matches exactly;
- 160/160 fresh contexts compile;
- WORLD-context bytes are identical across C00/C11/C10/C01 and bare cached control;
- phase boundary tokenization is deterministic and identical across paths;
- exactly 160 score sets complete for each C00/C11/C10/C01;
- exactly 160 bare cached BASE control score sets complete;
- every score set contains exactly the five frozen labels;
- cached-wrapper parity between bare cached BASE and C00 is exact for all 800 label comparisons;
- Phase A cache is reused without WORLD-context recomputation after switching adapter state;
- candidate cache cloning prevents cross-label contamination;
- runtime evidence records intended adapter state for both phases;
- first score set of C00/C11/C10/C01 and bare cached control repeats with exact serialized numeric equality;
- no model weight update;
- no simulation-state commit;
- no generation, retry, fallback, repair, EOS manipulation, scalar correction, calibration, or action hint;
- source P1C-v1/D1 frozen evidence remains untouched;
- evidence output is immutable and digest-addressed.

If G0 fails, G1–G5 are `NOT_EVALUABLE`.

## 12. G1 — decode-side WAIT induction

Primary sufficiency contrast:

`D_decode_base(c,i) = M_C01(c,i) - M_C00(c,i)`

G1 passes if:

- median `D_decode_base > 0`; and
- at least 75% of all 160 values are > 0.

Companion factorial contrast, reported without an additional pass threshold:

`D_decode_FA(c,i) = M_C11(c,i) - M_C10(c,i)`

G1 PASS means FA-v1 activity during selector/scoring continuation is sufficient to consistently increase WAIT margin when WORLD context was encoded by BASE.

## 13. G2 — prefill-side WAIT induction

Primary sufficiency contrast:

`D_prefill_base(c,i) = M_C10(c,i) - M_C00(c,i)`

G2 passes if:

- median `D_prefill_base > 0`; and
- at least 75% of all 160 values are > 0.

Companion factorial contrast, reported without an additional pass threshold:

`D_prefill_FA(c,i) = M_C11(c,i) - M_C01(c,i)`

G2 PASS means FA-v1 WORLD-context prefill alone is sufficient to carry a consistent WAIT-margin increase into BASE-only selector scoring.

## 14. G3 — structural replication and carryover

For each `S ∈ {S_msg,S_prop,S_owner}` define:

Full-adapter structural gain:

`A_full_S(i) = S_C11(i) - S_C00(i)`

Prefill-only structural carryover:

`A_prefill_S(i) = S_C10(i) - S_C00(i)`

For one structural contrast `S`, `FULL_GAIN(S)` passes if:

- median `A_full_S > 0`; and
- at least 75% of its 32 values are > 0.

`PREFILL_CARRYOVER(S)` passes under the same rule.

A structural contrast is a `REPLICATED_CARRYOVER(S)` only if both `FULL_GAIN(S)` and `PREFILL_CARRYOVER(S)` pass for that same contrast.

G3 passes if at least 2 of 3 structural contrasts are `REPLICATED_CARRYOVER`.

This prevents a carryover claim when the full-adapter structural gain itself does not replicate on the fresh cohort.

## 15. G4 — decoupling candidate

Define:

`R_wait(c,i) = M_C11(c,i) - M_C10(c,i)`

G4 passes only if all are true:

1. G3 passes;
2. median `R_wait > 0`;
3. at least 75% of all 160 `R_wait` values are > 0.

PASS interpretation is bounded to:

> Under one common cached execution topology, FA→BASE preserves replicated preregistered structural gain while reducing WAIT margin relative to FA→FA. This supports a separately versioned runtime architecture experiment.

G4 does not authorize deployment and does not establish autonomous policy competence.

## 16. G5 — latent rank-1 context sensitivity

For each condition C00/C11/C10/C01 separately:

- a matched case is sensitive if its five context-class rank-1 labels are not all identical;
- compute matched sensitivity rate over 32 case sets;
- compute TVD of each non-QUIET context-class rank-1 label distribution versus QUIET.

A condition passes G5 if:

- matched sensitivity rate >= `0.25`; and
- at least 2 of 4 non-QUIET context classes have TVD >= `0.25`.

Report G5 separately for all four conditions. G5 is diagnostic and cannot override G1–G4.

## 17. Predeclared factorial interaction diagnostics

P1C-v2 reports, without pass/fail thresholds:

WAIT interaction:

`I_wait(c,i) = M_C11(c,i) - M_C10(c,i) - M_C01(c,i) + M_C00(c,i)`

For each structural contrast `S`:

`I_S(i) = S_C11(i) - S_C10(i) - S_C01(i) + S_C00(i)`

For each interaction report count, median, mean, positive fraction, negative fraction, and zero fraction.

These quantify non-additivity between prefill and selector/scoring adapter activation. They are mechanistic diagnostics only and do not create new admission gates.

## 18. Frozen interpretation matrix

Provided G0 passes:

- G1 PASS, G2 FAIL: selector/scoring continuation is sufficient for consistent WAIT induction; prefill alone is not.
- G1 FAIL, G2 PASS: prefill alone is sufficient for consistent WAIT induction; decode-only activation is not.
- G1 PASS, G2 PASS: both isolated phases are sufficient to increase WAIT margin relative to C00.
- G1 FAIL, G2 FAIL: neither isolated phase is sufficient; full FA effect may depend on cross-phase interaction.
- G3 PASS, G4 PASS: strongest preregistered mechanistic evidence for a future phase-decoupled Foundation→Policy runtime experiment.
- G3 PASS, G4 FAIL: replicated structural carryover exists, but FA→BASE does not consistently reduce WAIT margin relative to FA→FA.
- G3 FAIL: replicated structural carryover through FA→BASE is not established on the fresh cohort.

Factorial interaction diagnostics refine, but never override, these gate interpretations.

## 19. Explicit non-claims

P1C-v2 cannot establish:

- Founder Freeze;
- autonomous policy competence;
- behavioral validity;
- that FA→BASE should be deployed;
- that BASE is an adequate action selector;
- that FA-v1 is policy-neutral;
- that all cached-vs-full numerical differences are solved generally;
- that D1's disabled-wrapper equality necessarily holds outside the frozen runtime/model/path;
- that operational phase attribution is equivalent to pure layer/module causal localization.

Founder Freeze remains `NOT_ESTABLISHED`.

## 20. Preservation and post-execution boundary

After the first P1C-v2 model forward:

- this preregistration is immutable;
- thresholds, cohort, labels, phase boundary, scoring topology, and gate definitions cannot change;
- failed/interrupted runs may not be overwritten or deleted;
- implementation defects require a separately versioned run/output root;
- post-hoc hidden-state probes, layer attribution, alternative precision, alternate selectors, generation, scalar correction, or policy-model substitution must be separately versioned;
- primary evidence must be canonically archived before any post-hoc analysis.

P1C-v1 and D1 frozen evidence remain historical and immutable.