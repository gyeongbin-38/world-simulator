# WORLD P1B Adapter–Selector Decomposition V1

Status: PRE-EXECUTION PREREGISTRATION — FROZEN BEFORE P1B MODEL INFERENCE

## 1. Purpose

P1 established valid measurement but found `NO_DIRECTED_ACTION` as both canonical I3 output and teacher-forced rank-1 label in all 80 tested contexts. A zero-inference post-hoc analysis then found that the complete five-label ranking never changed while sub-rank log probabilities did move with context.

P1B asks a narrower mechanistic question:

> Is the persistent `NO_DIRECTED_ACTION` selection primarily inherited from the base model/interface, amplified by FA-v1, or masking action-specific context signal that remains below a global decision boundary?

P1B is a researcher-side decomposition study. It is not a behavioral admission study and cannot establish social competence or Founder Freeze.

## 2. Known prior evidence and separation

Known before P1B and excluded from any new P1B denominator:

- A0 I3 motor/interface admission passed while producing `NO_DIRECTED_ACTION` across its R3 cohort.
- P0 passed infrastructure/causal-integrity gates while producing WAIT on all 72 cognition attempts.
- P1 primary result: `P1-G0 PASS`, `P1-G1 FAIL`, `P1-G2 FAIL`, classification `NO_CONTEXT_SENSITIVE_POLICY_EVIDENCE`.
- P1 post-hoc V1: full five-label ranking changed in 0 matched cases, but teacher-forced sub-rank action scores moved numerically with context.
- P1 post-hoc observed non-gated score movement is hypothesis-generating only and may not be reused as a P1B result.

P1B therefore uses a new held-out deterministic case-index range for confirmatory base-vs-FA score decomposition. A separate paired interface diagnostic may reuse the archived P1 contexts only for the new label-only interface measurement described below.

## 3. Scientific invariants

P1B preserves the WORLD research boundary:

- no predefined friend/enemy/leader/team/profession/family role;
- no trust, rank, mate score, cooperation reward, fitness target, or social desirability score;
- no synthetic affect or personality;
- no instruction to choose SEND, PROPOSE, ACCEPT, REJECT, or WAIT;
- no action-frequency reward;
- no simulation state commit;
- no model weight update;
- no retry, fallback, repair, EOS suppression, or min-new-token workaround;
- deterministic contexts are compiled before model measurements;
- all score manipulation is researcher-side analysis and never enters agent-visible context;
- P1B results cannot retroactively alter A0, P0, or P1.

## 4. Frozen deployment identities

Shared base deployment:

- repository: `allenai/OLMo-2-0425-1B-Instruct`
- revision: `48d788eca847d4d7548f375ad03d3c9312f6139e`
- checkpoint SHA-256: `36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f`
- tokenizer digest: `c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff`
- BF16
- Python 3.12.3
- torch 2.7.1+cu118
- transformers 5.16.1
- peft 0.20.0
- lm-format-enforcer 0.11.3
- canonical pip-freeze SHA-256: `a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf`
- NVIDIA A40, compute capability 8.6

Two frozen model conditions:

### B0 — BASE_ONLY

Exact base checkpoint with no PEFT adapter loaded.

### B1 — FA_V1

Exact base checkpoint plus:

- adapter artifact: `F0_FA_V1_FORMAL`
- adapter SHA-256: `46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec`
- adapter config SHA-256: `687100a0b6340b6096ca1e86066d3c13224b3c8e14ce9fb1b0cf78a52a8bdb7d`

No parameter may be updated in either condition.

## 5. Context cohorts

P1B uses the existing R3 fixture semantics without additional diagnostic wording.

Context classes:

1. `QUIET`
2. `MESSAGE_RECEIVED`
3. `PROPOSAL_RECEIVED`
4. `OWN_PROPOSAL_PENDING`
5. `RECENT_INTERACTION`

### Cohort H — held-out confirmatory cohort

- case indices: 1000–1031 inclusive
- 32 deterministic matched case sets
- 5 context classes × 32 = 160 contexts
- these case indices were not used in P1 primary or P1 post-hoc analysis

The case variants are deterministic robustness variants, not independent population samples. Consistency thresholds below are engineering/confirmatory rules, not claims of frequentist population significance.

### Cohort P — archived-P1 interface-pair cohort

- case indices: 0–15 inclusive
- 5 context classes × 16 = 80 contexts
- used only for a new label-only interface diagnostic paired conceptually with the already archived P1 I3 result
- archived P1 I3 outputs are read-only evidence; they are not regenerated or replaced

## 6. Identical-input requirement

Within a matched context, B0 and B1 must receive byte-identical rendered base context input before any researcher-only scoring/generation suffix.

The runner must record and verify identical rendered-input SHA-256 for B0/B1. Model-profile identifiers or evidence provenance must not create model-visible input differences between conditions.

Failure of this requirement makes base-vs-FA attribution `NOT_EVALUABLE`.

## 7. Measurement A — teacher-forced five-label scoring

On every Cohort H context, both B0 and B1 receive the same frozen researcher diagnostic prefix used by P1:

`\nAction selection JSON:\n{"action_label":"`

The complete canonical five-label set is scored teacher-forced:

- `NO_DIRECTED_ACTION`
- `DIRECT_TEXT`
- `OPEN_BILATERAL_REQUEST`
- `CONFIRM_BILATERAL_REQUEST`
- `DECLINE_BILATERAL_REQUEST`

For every label, record:

- token IDs;
- total sequence log probability;
- mean log probability per label token;
- complete rank ordering.

No scored label is executed or committed.

## 8. Measurement B — label-only constrained greedy selector

P1B introduces a researcher-only selector diagnostic that removes action payload serialization while preserving autonomous label choice.

Rendered suffix:

`\nAction selection JSON:\n`

Constraint schema contains exactly one required field:

`action_label`

whose enum is the five canonical labels above. No target, body, proposal ID, direction, or other payload field is generated.

Generation policy:

- greedy decoding;
- no sampling;
- no retry/fallback/repair;
- no EOS suppression;
- no chat template;
- max-new-tokens sufficient only for the one-field JSON object and frozen before execution;
- same seed identity as WORLD deterministic diagnostic runs, although greedy decoding must not depend on sampling randomness.

Measurement B runs:

- B0 and B1 on all 160 Cohort H contexts;
- B1 on all 80 Cohort P contexts for direct interface comparison with archived P1 I3 behavior.

These label-only outputs are diagnostics only and are never converted into WORLD state commits.

## 9. Frozen score definitions

Let `L_m(a,c,i)` be the teacher-forced total log probability of action label `a` for model condition `m`, context class `c`, and case index `i`.

Let `W = NO_DIRECTED_ACTION` and let `D` be the four directed labels.

### 9.1 Directed-relative-to-WAIT score

For directed action `a`:

`r_m(a,c,i) = L_m(a,c,i) - L_m(W,c,i)`

Larger values mean the directed label is more competitive with WAIT.

### 9.2 Global WAIT margin

`M_m(c,i) = L_m(W,c,i) - max_{a in D} L_m(a,c,i)`

Positive values indicate WAIT outranks every directed label by total sequence log probability.

### 9.3 Within-directed centered score

`q_m(a,c,i) = r_m(a,c,i) - mean_{d in D} r_m(d,c,i)`

This removes the context-wide mean directed-vs-WAIT shift and isolates relative preference within the four directed labels.

### 9.4 MESSAGE specificity

For each held-out case `i`:

`S_msg_m(i) = q_m(DIRECT_TEXT, MESSAGE_RECEIVED, i) - q_m(DIRECT_TEXT, QUIET, i)`

Positive values mean `DIRECT_TEXT` gains relative to the other directed labels when an incoming message is present.

### 9.5 Proposal-response family separation

Define response family:

`R = {CONFIRM_BILATERAL_REQUEST, DECLINE_BILATERAL_REQUEST}`

and comparison family:

`O = {DIRECT_TEXT, OPEN_BILATERAL_REQUEST}`.

For any context `c`:

`F_m(c,i) = mean_{a in R} q_m(a,c,i) - mean_{a in O} q_m(a,c,i)`

Proposal-received specificity:

`S_prop_m(i) = F_m(PROPOSAL_RECEIVED,i) - F_m(QUIET,i)`

Positive values mean proposal-response labels gain relative to the other directed labels when an incoming proposal exists.

### 9.6 Proposal ownership/direction specificity

`S_owner_m(i) = F_m(PROPOSAL_RECEIVED,i) - F_m(OWN_PROPOSAL_PENDING,i)`

Positive values mean proposal-response labels are relatively more competitive for an incoming proposal than for the actor's own pending proposal.

### 9.7 Adapter WAIT-margin effect

`A_wait(c,i) = M_FA_V1(c,i) - M_BASE_ONLY(c,i)`

Positive values mean FA-v1 increases the total-log-probability separation of WAIT from the best directed label.

### 9.8 Adapter structural-signal gain

For each structural contrast `S in {S_msg, S_prop, S_owner}`:

`A_S(i) = S_FA_V1(i) - S_BASE_ONLY(i)`

Positive values mean FA-v1 strengthens that context/action-specific contrast relative to the exact base model.

## 10. Integrity gate P1B-G0

P1B mechanistic interpretation is valid only if all are true:

- static deployment identity passes for both B0 and B1;
- all 160 Cohort H rendered inputs are byte-identical across B0/B1;
- 160/160 B0 teacher-forced score sets complete;
- 160/160 B1 teacher-forced score sets complete;
- every score set contains exactly the five canonical labels;
- 160/160 B0 label-only generations complete;
- 160/160 B1 label-only generations complete;
- 80/80 B1 Cohort P label-only generations complete;
- zero model weight updates;
- zero simulation state commits;
- evidence artifacts are complete and digest-addressed;
- exact repeat checks for the first B0 and B1 score request are numerically identical under the runner's frozen equality rule;
- exact repeat checks for the first B0 and B1 label-only generation have identical raw-generation CAS digests.

If P1B-G0 fails, all causal attribution classifications are `NOT_EVALUABLE`.

## 11. Interface-collapse diagnostic P1B-G1

This gate tests whether typed payload serialization is necessary for the observed FA-v1 WAIT dominance.

P1B-G1 passes if, on Cohort P under B1 label-only generation:

- overall `NO_DIRECTED_ACTION` rate >= 0.95, and
- every context-class `NO_DIRECTED_ACTION` rate >= 0.90.

If P1B-G1 passes, interpretation is limited to:

> WAIT dominance persists even when typed action payload generation is removed; typed payload serialization is therefore not necessary to produce the tested WAIT-dominant selector behavior.

It does not prove that I3 has zero effect.

## 12. Adapter WAIT-amplification diagnostic P1B-G2

Across all 160 Cohort H matched contexts, P1B-G2 passes if:

1. median `A_wait > 0`, and
2. at least 75% of matched contexts have `A_wait > 0`.

If P1B-G2 passes, FA-v1 is classified as consistently amplifying WAIT margin relative to the exact base model under the tested scoring interface.

If it fails, no adapter-induced WAIT amplification is established.

## 13. Structural selectivity diagnostics P1B-G3

Each structural contrast is evaluated separately for FA-v1 on the 32 held-out matched case sets.

A contrast is `FA_STRUCTURALLY_PRESENT` if:

1. its median is > 0, and
2. at least 75% of the 32 case values are > 0.

Apply independently to:

- `S_msg_FA_V1`
- `S_prop_FA_V1`
- `S_owner_FA_V1`

P1B-G3 summary passes if at least 2 of these 3 structural contrasts are `FA_STRUCTURALLY_PRESENT`.

Passing P1B-G3 establishes only action-structure-aligned latent score discrimination after removing generic directed-vs-WAIT movement. It does not establish autonomous policy competence.

## 14. Adapter structural-gain diagnostic P1B-G4

For each structural contrast, adapter gain `A_S` is `ADAPTER_GAIN_PRESENT` if:

1. median `A_S > 0`, and
2. at least 75% of the 32 matched case values have `A_S > 0`.

P1B-G4 summary passes if at least 2 of the 3 structural contrasts show `ADAPTER_GAIN_PRESENT`.

Passing P1B-G4 means FA-v1 strengthens context/action-specific latent score structure relative to the exact base model on the held-out cohort.

## 15. Label-only generated sensitivity P1B-G5

For B0 and B1 separately on Cohort H, compute the same non-normative matched context-sensitivity structure used by P1:

- matched case is sensitive if the five context-class label-only outputs are not all identical;
- matched sensitivity rate = sensitive case sets / 32;
- compare each non-QUIET class label distribution with QUIET by TVD.

A model condition passes generated label-only sensitivity if:

1. matched sensitivity rate >= 0.25, and
2. at least 2 of 4 non-QUIET classes have TVD from QUIET >= 0.25.

No particular label is required.

P1B-G5 is reported separately for B0 and B1 and is not an admission gate for WORLD behavior.

## 16. Frozen interpretation matrix

Provided P1B-G0 passes:

### G1 PASS

WAIT dominance is not dependent on typed payload serialization under the paired tested contexts.

### G2 PASS, G3/G4 FAIL

FA-v1 primarily appears to strengthen a global WAIT/calibration prior without establishing held-out action-specific structural gain.

### G2 FAIL, G3 PASS, G4 PASS

FA-v1 adds held-out action-structure-aligned latent signal without consistently increasing the global WAIT margin. The remaining rank-1 collapse is more consistent with an inherited/global decision boundary or other selector calibration issue than with loss of context grounding.

### G2 PASS, G3 PASS, G4 PASS

FA-v1 both adds action-structure-aligned latent signal and consistently strengthens WAIT margin. This would support a two-effect explanation: improved grounding coexisting with adverse selector calibration.

### G3 FAIL and G4 FAIL

No held-out action-specific latent selector structure is established by P1B; generic interaction sensitivity or non-specific score movement remains the stronger explanation.

### B0 G5 PASS, B1 G5 FAIL

FA-v1 suppresses generated label-only context sensitivity relative to the base under the tested interface.

### B0 G5 FAIL, B1 G5 PASS

FA-v1 adds generated label-only context sensitivity relative to the base.

### both G5 FAIL

Neither model condition establishes generated label-only context-sensitive selection under the tested cohort.

These outcomes may coexist with G2–G4 and must be reported jointly rather than collapsed into a single success/failure label.

## 17. Descriptive non-gates

Report but do not use as independent admission criteria:

- action frequency;
- full rank order;
- individual log probabilities;
- mean-token-normalized score variants;
- generic directed activation relative to QUIET;
- entropy;
- apparent social desirability or semantic interpretation beyond the structural contrasts explicitly preregistered above.

## 18. Founder Freeze boundary

P1B cannot establish Founder Freeze.

Even if latent structural signal is found, any selector calibration, residualization, WAIT-prior subtraction, new action head, new constraint, pointer interface, or retraining would be a separately versioned intervention requiring its own admission study before use in a WORLD founder run.

## 19. Failure handling

After the first P1B model forward pass begins:

- preserve all evidence on failure;
- do not overwrite the primary P1B output root;
- do not replace a failed primary run with an unversioned rerun;
- distinguish infrastructure, implementation, and scientific failure;
- any code/measurement defect requires a separately versioned rerun;
- any prompt/schema/threshold/model change requires a new preregistration or explicit protocol amendment before further inference.

## 20. Pre-execution gate

P1B model inference is forbidden until:

1. this preregistration is committed;
2. a machine-readable P1B config is committed after or with the preregistration and matches this document;
3. P1B measurement code is committed after the preregistration;
4. pure metric/unit tests pass;
5. runner syntax/import checks pass;
6. exact static deployment preflight passes for B0 and B1;
7. validate-only preflight passes against the exact runner commit;
8. output root is fresh and empty.
