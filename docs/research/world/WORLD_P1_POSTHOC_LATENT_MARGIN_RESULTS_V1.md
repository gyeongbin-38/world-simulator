# WORLD P1 Post-hoc Latent Margin Results V1

Status: POST-HOC EXPLORATORY RESULTS — FROZEN, NO P1 GATE EFFECT

## 1. Purpose and boundary

This document freezes a post-hoc exploratory analysis of the already archived `WORLD_P1_CONTEXT_SENSITIVE_POLICY_V1` evidence.

The analysis performs **zero model inference** and does not alter P1 gates. It reads the stored teacher-forced five-label score vectors and asks whether context changes sub-rank action scores even though `NO_DIRECTED_ACTION` remained rank-1 for all 80 P1 contexts.

P1 remains:

- `P1-G0 = PASS`
- `P1-G1 = FAIL`
- `P1-G2 = FAIL`
- classification `NO_CONTEXT_SENSITIVE_POLICY_EVIDENCE`

## 2. Source identity

Authoritative primary P1 evidence:

- P1 summary SHA-256: `3d0627c3dbe874a3da512c2a1273f1bfb8069cbf0cab069a79de5b7858a07bc1`
- P1 result digest: `90552c4bc38cdfbc882d96954c0f00d8cdb193896cc686eed4b70788c213b847`
- P1 canonical archive SHA-256: `240f372f2733b69413c6f161a48ef54f99fcba656ec341501ad059f5be2281d0`
- primary runner commit: `3604290314d0bf1a780cae9c5c09e0f7db925437`

Post-hoc analyzer:

- script: `tools/world_p1_posthoc_margin_analysis.py`
- analyzer commit: `10b984efb994a1e823833362cb298b02fd4fd61f`
- analysis ID: `WORLD_P1_POSTHOC_LATENT_MARGIN_V1`
- analysis digest: `4564ad3f3ed53a043c118bf98ce7367307b19c374e0d421f20f73b5497b2a734`
- generated analysis JSON SHA-256: `9491175969b0395c10c7c270dd1811475afc171fb790311efd793f2bf84bfafb`

## 3. Method

For each P1 context and action label, the stored teacher-forced total log probability is compared with `NO_DIRECTED_ACTION`.

For each non-QUIET context and matched case index, the analysis computes differences relative to the matched `QUIET` case.

For directed action `a`, a positive relative-total delta means that action became more competitive with `NO_DIRECTED_ACTION` than it was in the matched QUIET context.

For the WAIT margin, a negative delta means the best directed action moved closer to `NO_DIRECTED_ACTION`.

This is descriptive only. Token-length effects remain possible because the primary score is full-label sequence log probability. Mean-token-normalized values are retained as secondary descriptions but were not P1 gates.

## 4. Full-rank stability

Full five-label ranking changed relative to matched QUIET in **0/16 cases for every non-QUIET context class**:

- `MESSAGE_RECEIVED`: 0.0
- `PROPOSAL_RECEIVED`: 0.0
- `OWN_PROPOSAL_PENDING`: 0.0
- `RECENT_INTERACTION`: 0.0

Therefore P1's score vectors are **rank-stable** across these context interventions.

## 5. Mean WAIT-margin movement vs QUIET

Mean change in total-log-probability WAIT margin:

- `MESSAGE_RECEIVED`: `-0.810028076171875`
- `PROPOSAL_RECEIVED`: `+0.372406005859375`
- `OWN_PROPOSAL_PENDING`: `+0.35626220703125`
- `RECENT_INTERACTION`: `-0.3019256591796875`

Interpretation of sign only:

- negative: the best directed action became closer to `NO_DIRECTED_ACTION`;
- positive: `NO_DIRECTED_ACTION` became more separated from the best directed action.

Thus the score vectors are not numerically flat even though rank ordering never changes.

## 6. Mean directed-label movement relative to WAIT

### MESSAGE_RECEIVED

- `CONFIRM_BILATERAL_REQUEST`: `+0.084442138671875`
- `DECLINE_BILATERAL_REQUEST`: `+0.561004638671875`
- `DIRECT_TEXT`: `+0.810028076171875`
- `OPEN_BILATERAL_REQUEST`: `+1.096160888671875`

All four directed labels become more competitive with WAIT on average.

### PROPOSAL_RECEIVED

- `CONFIRM_BILATERAL_REQUEST`: `-0.056976318359375`
- `DECLINE_BILATERAL_REQUEST`: `+0.357086181640625`
- `DIRECT_TEXT`: `-0.372406005859375`
- `OPEN_BILATERAL_REQUEST`: `+0.372711181640625`

The movement is mixed rather than cleanly concentrated on the proposal-response labels.

### OWN_PROPOSAL_PENDING

- `CONFIRM_BILATERAL_REQUEST`: `-0.28009033203125`
- `DECLINE_BILATERAL_REQUEST`: `+0.11053466796875`
- `DIRECT_TEXT`: `-0.35626220703125`
- `OPEN_BILATERAL_REQUEST`: `+0.46405029296875`

Again the movement is mixed.

### RECENT_INTERACTION

- `CONFIRM_BILATERAL_REQUEST`: `+0.1349334716796875`
- `DECLINE_BILATERAL_REQUEST`: `+0.2696990966796875`
- `DIRECT_TEXT`: `+0.3019256591796875`
- `OPEN_BILATERAL_REQUEST`: `+0.6017303466796875`

All four directed labels become more competitive with WAIT on average.

## 7. Exploratory interpretation

The strongest supported post-hoc description is:

> **rank-stable but score-sensitive WAIT dominance**

The tested FA-v1/R3 contexts produce measurable movement in teacher-forced action scores while preserving the same complete action ranking and the same rank-1 label in every matched case.

This reduces support for the strongest version of the hypothesis that context information is completely absent before action selection. Some context-dependent signal reaches the action-score layer.

However, this analysis does **not** establish an action-specific autonomous selector. In particular, `PROPOSAL_RECEIVED` does not show a simple, uniquely proposal-response-aligned shift. The observed movement may contain generic interaction sensitivity, action-label calibration effects, or other structured but insufficient signals.

The analysis also does not prove that I3 codec serialization is irrelevant. It only shows that WAIT dominance is already present in the teacher-forced label-scoring layer, before typed payload generation can by itself explain the entire collapse.

## 8. Process deviation and evidence authority

The post-hoc JSON was written into the working P1 output directory after the primary P1 canonical archive had already been created and verified. The analyzer's intended separation was to avoid writing into the primary P1 root, so this location choice is recorded as a process-level deviation.

It does not mutate the authoritative primary evidence because:

1. the canonical P1 archive predates the post-hoc file;
2. that archive had already been reported extraction/content verified;
3. primary P1 summary/result hashes are frozen independently;
4. the post-hoc file is explicitly excluded from P1 gates.

Future derived analyses must use a separate analysis output root.

## 9. Consequence for the next study

The next confirmatory experiment should not simply rerun P1 or introduce retraining immediately.

A separately preregistered selector diagnostic should distinguish at least these hypotheses:

1. **global WAIT/calibration prior with real context signal**;
2. **generic interaction sensitivity without action-specific discrimination**;
3. **action-specific latent selector signal that remains below the current decision boundary**;
4. **interface/serialization effects layered on top of the above**.

Any new selector, pointer, constraint, prompt, calibration, or training intervention is a new study and cannot retroactively alter P1.

## 10. Frozen post-hoc statement

**P1 post-hoc V1: zero-inference exploratory analysis finds rank-stable but score-sensitive WAIT dominance. Context affects stored action scores, but no rank change or preregistered context-sensitive policy competence is established. P1-G0/G1/G2 remain unchanged.**
