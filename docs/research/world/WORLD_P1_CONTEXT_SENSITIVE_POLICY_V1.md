# WORLD P1 Context-Sensitive Policy Study V1

Status: PRE-EXECUTION PREREGISTRATION — FROZEN BEFORE P1 EXECUTION

## 1. Purpose

P0 established bounded end-to-end WORLD infrastructure and causal integrity under the accepted FA-v1 + I3 path, while both P0 replicas produced WAIT on all 72 cognition attempts.

P1 asks a narrower scientific question:

> Does exact FA-v1 exhibit nontrivial context-sensitive action preference under the already admitted I3 interface, and is any such preference visible in teacher-forced action-label ranking even when free generation remains WAIT-dominant?

P1 is a confirmatory policy-sensitivity study. It is not a social-behavior benchmark and does not reward any particular action.

## 2. Prior observations and separation from the denominator

The following are known before P1 and are not part of the P1 denominator:

- A0 I3 established codec/domain/motor competence but produced WAIT / NO_DIRECTED_ACTION across its frozen R3 context cohort.
- P0 produced WAIT on 72/72 real-model cognition attempts across two completion-order replicas.
- prior secondary diagnostics found NO_DIRECTED_ACTION rank-1 in a smaller teacher-forced state cohort.

P1 is therefore a confirmatory study, not a discovery claim. Thresholds below are frozen before P1 generation.

## 3. Scientific invariants

P1 preserves WORLD invariants:

- no predefined friend/enemy/leader/team/profession/family role;
- no friendship, trust, rank, mate score, cooperation reward, or social desirability target;
- no synthetic affect/personality baseline;
- no resource reward or task objective;
- no instruction to SEND, PROPOSE, ACCEPT, REJECT, or WAIT;
- no hidden action-frequency target in the prompt;
- model output remains a candidate action only;
- deterministic WORLD law remains external;
- no simulation state commit occurs in P1;
- no retry, fallback, output repair, EOS suppression, or min_new_tokens workaround;
- action identity is measured, not normatively scored.

## 4. Deployment identity

Exact accepted deployment:

- base: allenai/OLMo-2-0425-1B-Instruct
- base revision: `48d788eca847d4d7548f375ad03d3c9312f6139e`
- base checkpoint SHA-256: `36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f`
- tokenizer digest: `c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff`
- FA-v1 adapter SHA-256: `46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec`
- Python 3.12.3
- torch 2.7.1+cu118
- CUDA runtime 11.8
- cuDNN 90100
- transformers 5.16.1
- peft 0.20.0
- lm-format-enforcer 0.11.3
- GPU NVIDIA A40, compute capability 8.6
- dtype BF16
- canonical pip-freeze SHA-256: `a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf`

## 5. Context cohort

P1 reuses the frozen R3 researcher fixtures without adding diagnostic wording.

Five context classes:

1. `QUIET`
2. `MESSAGE_RECEIVED`
3. `PROPOSAL_RECEIVED`
4. `OWN_PROPOSAL_PENDING`
5. `RECENT_INTERACTION`

Each class has 16 deterministic case variants, indexed 0–15.

Total primary contexts:

- 5 classes × 16 cases = 80 contexts.

For a given case index, the five classes form a matched context set. The case index changes opaque message/proposal identifiers but does not add behavioral instructions.

## 6. Measurement layer A — canonical I3 generation

For every context, P1 runs exact FA-v1 using the already admitted I3 interface:

- neutral suffix: `\nAction selection JSON:\n`
- action-conditional typed JSON schema
- lm-format-enforcer constraint
- greedy decoding
- max_new_tokens 128
- no sampling
- seed identity frozen to the existing WORLD seed value `35020260831`
- no chat template
- no retry/fallback/repair

P1 records:

- candidate action label;
- typed codec/domain/commit validity;
- raw text and token IDs via CAS-backed cognition evidence;
- context class and matched case index;
- first-token EOS;
- evidence completeness.

No P1 action is committed to simulation state.

## 7. Measurement layer B — teacher-forced action-label ranking

On the same 80 compiled base contexts, P1 performs researcher-only teacher-forced scoring of the five canonical model-facing action labels.

This measurement:

- does not generate an action;
- does not mutate state;
- does not enter the agent-visible context;
- uses the existing frozen researcher diagnostic prefix `\nAction selection JSON:\n{"action_label":"`;
- records the complete rank ordering and rank-1 label;
- is diagnostic evidence only.

Layer B is intended to distinguish:

- no latent context-dependent action preference, from
- a latent context-dependent preference that is not expressed by canonical I3 generation.

## 8. Integrity gate P1-G0

P1 policy interpretation is valid only if all of the following hold:

- 80/80 canonical I3 attempts complete without infrastructure failure;
- codec-valid rate = 1.0;
- domain-valid rate = 1.0;
- evidence-complete rate = 1.0;
- first-token EOS rate = 0.0;
- exact repeat of the first canonical request has identical raw-generation CAS digest;
- all 80 teacher-forced ranking measurements complete;
- no model weight update occurs.

If P1-G0 fails, policy sensitivity is `NOT_EVALUABLE`.

## 9. Generated policy-sensitivity gate P1-G1

P1-G1 measures action-selection sensitivity without assigning desirability to an action.

For each matched case index `i`, define generated matched sensitivity as true when the five generated candidate labels across the five context classes contain more than one distinct label.

Define:

- `generated_matched_sensitivity_rate` = sensitive matched case sets / 16.

For each non-QUIET context class, compare its 16-label empirical distribution with the 16-label QUIET distribution using total variation distance (TVD).

P1-G1 passes only if both are true:

1. `generated_matched_sensitivity_rate >= 0.25` (at least 4/16 matched case sets differ by context), and
2. at least 2 of the 4 non-QUIET classes have `TVD(label_distribution, QUIET) >= 0.25`.

These thresholds measure context dependence only. No specific action label is required.

## 10. Latent rank-1 sensitivity gate P1-G2

P1-G2 applies the same non-normative sensitivity structure to teacher-forced rank-1 labels.

For each matched case index `i`, define latent matched sensitivity as true when the five teacher-forced rank-1 labels contain more than one distinct label.

Define:

- `latent_matched_sensitivity_rate` = sensitive matched case sets / 16.

For each non-QUIET context class, compare its 16 rank-1 labels with QUIET using TVD.

P1-G2 passes only if both are true:

1. `latent_matched_sensitivity_rate >= 0.25`, and
2. at least 2 of the 4 non-QUIET classes have rank-1 TVD from QUIET >= 0.25.

The full ranking orders and label log probabilities are retained descriptively, but only rank-1 labels enter P1-G2.

## 11. Frozen interpretation matrix

Provided P1-G0 passes:

### G1 PASS, G2 PASS

Interpretation:

- nontrivial context-sensitive policy competence is established under canonical I3;
- teacher-forced preference is directionally consistent with the existence of context-sensitive policy signal.

### G1 PASS, G2 FAIL

Interpretation:

- generated context-sensitive policy competence is established under canonical I3;
- teacher-forced rank-1 diagnostic does not independently establish latent sensitivity.

### G1 FAIL, G2 PASS

Interpretation:

- canonical I3 does not establish generated context-sensitive policy competence;
- latent context-sensitive action preference is present;
- interface/serialization suppression becomes a priority hypothesis for a separately versioned selector/interface study.

### G1 FAIL, G2 FAIL

Interpretation:

- P1 finds no evidence of nontrivial context-sensitive action preference in the tested FA-v1/R3 cohort;
- canonical I3 generated policy competence remains NOT_ESTABLISHED;
- a later selector/interface diagnostic may still test codec-induced collapse, but cannot retroactively change P1.

## 12. Descriptive non-gates

The following are reported but are not independent gates:

- WAIT frequency;
- SEND frequency;
- PROPOSE frequency;
- ACCEPT frequency;
- REJECT frequency;
- exact label counts by context class;
- full teacher-forced rank ordering;
- individual log probabilities;
- action-label entropy;
- apparent social interpretation of any action.

No post-hoc action-frequency requirement may be introduced.

## 13. Founder Freeze boundary

P1 alone does not establish Founder Freeze.

Founder Freeze remains `NOT_ESTABLISHED` unless separately admitted after the required policy/interface evidence and subsequent experimental criteria are satisfied.

## 14. Failure handling

After the first P1 model generation begins:

- preserve raw evidence on any failure;
- do not delete or overwrite the primary output root;
- do not rerun a failed primary execution as a replacement;
- classify infrastructure vs implementation vs scientific failure;
- code/measurement defects require a separately versioned rerun;
- semantic interface changes require a separately preregistered study.

## 15. Pre-execution gate

P1 execution is forbidden until:

1. this preregistration is committed;
2. exact deployment/runtime static preflight passes;
3. P1 measurement code is committed after this preregistration;
4. P1 pure measurement tests pass;
5. P1 runner syntax/import checks pass;
6. P1 validate-only preflight passes against the exact runner commit.
