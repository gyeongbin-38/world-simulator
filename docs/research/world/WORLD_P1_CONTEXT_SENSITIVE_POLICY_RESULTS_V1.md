# WORLD P1 Context-Sensitive Policy Results V1

Status: POST-EXECUTION PRIMARY RESULTS — FROZEN

## 1. Scope

This document freezes the primary results of `WORLD_P1_CONTEXT_SENSITIVE_POLICY_V1` exactly as executed under the preregistered P1 protocol. It does not incorporate later exploratory post-hoc analysis into P1 gates.

P1 asked whether exact FA-v1 exhibits nontrivial context-sensitive action preference under the already admitted I3 interface, and whether any such preference appears in teacher-forced action-label rank-1 results even when canonical generation remains WAIT-dominant.

## 2. Execution identity

- preregistration: `docs/research/world/WORLD_P1_CONTEXT_SENSITIVE_POLICY_V1.md`
- preregistration commit: `eac7d109ea8f84ece9ac4c0f57e4e1882a55e9eb`
- runner: `tools/world_p1_context_sensitive_policy.py`
- primary runner commit: `3604290314d0bf1a780cae9c5c09e0f7db925437`
- configuration: `docs/research/world/WORLD_P1_CONTEXT_SENSITIVE_POLICY_CONFIG_V1.json`
- configuration SHA-256: `0f7c087e084ab3d2f9f5048046d392117b98b514747436a3b3d0f391da96ade1`
- canonical runtime pip-freeze SHA-256: `a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf`
- base checkpoint SHA-256: `36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f`
- tokenizer digest: `c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff`
- adapter SHA-256: `46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec`

Pre-execution checks recorded before primary generation:

- P1 pure measurement tests: `5 passed`
- runner syntax/import check: `P1_RUNNER_SYNTAX_IMPORT_OK`
- validate-only status: `P1_STATIC_PREFLIGHT_OK`

No claim is made here that the repository full test suite passed.

## 3. Primary evidence identity

Primary output root at execution time:

`/workspace/alifelm/evidence/WORLD_P1_CONTEXT_SENSITIVE_POLICY_V1_3604290`

Frozen identities:

- `summary.json` SHA-256: `3d0627c3dbe874a3da512c2a1273f1bfb8069cbf0cab069a79de5b7858a07bc1`
- primary stdout SHA-256: `b8fc60ccb3280debdb6e01b38bce16729d3b365e932090cc2fc6fb26e626a091`
- internal P1 result digest: `90552c4bc38cdfbc882d96954c0f00d8cdb193896cc686eed4b70788c213b847`
- canonical archive: `WORLD_P1_CONTEXT_SENSITIVE_POLICY_V1_3604290_CANONICAL.tar.gz`
- canonical archive SHA-256: `240f372f2733b69413c6f161a48ef54f99fcba656ec341501ad059f5be2281d0`

The canonical archive was created and archive extraction/content comparison was reported verified before any later exploratory post-hoc output was added to the working P1 directory. Therefore the archive above is the authoritative frozen copy of primary P1 evidence.

## 4. Cohort

P1 completed the frozen five-class R3 cohort:

- `QUIET`: 16
- `MESSAGE_RECEIVED`: 16
- `PROPOSAL_RECEIVED`: 16
- `OWN_PROPOSAL_PENDING`: 16
- `RECENT_INTERACTION`: 16

Total: 80 primary contexts.

Each context received both:

1. canonical I3 generation, and
2. teacher-forced five-label action ranking.

No P1 candidate action was committed to simulation state.

## 5. Frozen gate results

### P1-G0 — integrity

**PASS**

The frozen runner's integrity condition requires all of the following simultaneously: 80 complete primary attempts, 80 codec-valid attempts, 80 domain-valid attempts, 80 evidence-complete attempts, zero first-token EOS failures, 80 teacher-forced measurements, and byte-identical raw-generation CAS identity for the preregistered first-request repeat.

P1 returned:

`"P1-G0": true`

Therefore the P1 policy measurements are evaluable under the preregistered protocol.

### P1-G1 — generated context sensitivity

**FAIL**

Canonical I3 generated the same candidate label in every context:

- `QUIET`: `NO_DIRECTED_ACTION` 16/16
- `MESSAGE_RECEIVED`: `NO_DIRECTED_ACTION` 16/16
- `PROPOSAL_RECEIVED`: `NO_DIRECTED_ACTION` 16/16
- `OWN_PROPOSAL_PENDING`: `NO_DIRECTED_ACTION` 16/16
- `RECENT_INTERACTION`: `NO_DIRECTED_ACTION` 16/16

Thus the preregistered matched-sensitivity and distribution-shift gate did not pass.

### P1-G2 — latent rank-1 context sensitivity

**FAIL**

Teacher-forced rank-1 was also identical in every context:

- `QUIET`: `NO_DIRECTED_ACTION` 16/16
- `MESSAGE_RECEIVED`: `NO_DIRECTED_ACTION` 16/16
- `PROPOSAL_RECEIVED`: `NO_DIRECTED_ACTION` 16/16
- `OWN_PROPOSAL_PENDING`: `NO_DIRECTED_ACTION` 16/16
- `RECENT_INTERACTION`: `NO_DIRECTED_ACTION` 16/16

Thus the preregistered latent rank-1 sensitivity gate did not pass.

## 6. Frozen classification

Primary runner classification:

`NO_CONTEXT_SENSITIVE_POLICY_EVIDENCE`

Formal interpretation:

> P1 finds no evidence of nontrivial context-sensitive action preference in the tested exact FA-v1/R3 cohort under the preregistered generated-action and teacher-forced rank-1 gates.

Accordingly:

- canonical I3 context-sensitive generated policy competence: **NOT_ESTABLISHED**
- teacher-forced rank-1 context-sensitive action preference: **NOT_ESTABLISHED**
- Founder Freeze: **NOT_ESTABLISHED**

This result does not invalidate A0 motor/interface admission or P0 infrastructure/causal-integrity results. Those studies tested different claims.

## 7. What P1 does not establish

P1 does not establish that:

- the model contains no context information internally;
- every sub-rank action score is context-invariant;
- I3 alone is the unique cause of WAIT dominance;
- retraining is required;
- any social behavior is absent in all possible WORLD configurations;
- a particular directed action should have been selected.

Those stronger claims are outside the preregistered P1 gates.

## 8. Separation from later exploratory analysis

After this primary result was archived, a separate zero-inference exploratory analysis inspected the stored full teacher-forced score vectors. That analysis is not part of P1-G0/G1/G2 and cannot alter this result.

Its results are frozen separately in:

`docs/research/world/WORLD_P1_POSTHOC_LATENT_MARGIN_RESULTS_V1.md`

## 9. Final P1 statement

**WORLD P1 V1: measurement integrity PASS; generated context sensitivity FAIL; latent rank-1 context sensitivity FAIL; classification `NO_CONTEXT_SENSITIVE_POLICY_EVIDENCE`; Founder Freeze NOT_ESTABLISHED.**
