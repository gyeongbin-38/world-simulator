# WORLD P1C Foundation–Policy Phase Ablation — Results Freeze V1

Status: **PRIMARY MEASUREMENT FROZEN — BASE-WRAPPER EQUIVALENCE FAIL**

This document freezes the primary outcome of `WORLD_P1C_FOUNDATION_POLICY_PHASE_ABLATION_V1` before any post-hoc diagnostic work.

## Frozen execution identity

- Branch: `p1c-foundation-policy-phase-ablation`
- Runner commit: `f2e9e4dc9e7cdee6034ff33c663ffe434fa7c6ae`
- Preregistration commit: `8573d7a57c0a24bf480cb149d457d491e6a9d2ae`
- P1C config SHA-256: `1ee7e53e8e8efd67e9868702138e89bf2532e737fa41329ad276c8a10ef98589`
- Runtime pip-freeze SHA-256: `a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf`
- Runtime package count: `60`
- Base checkpoint SHA-256: `36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f`
- Base revision: `48d788eca847d4d7548f375ad03d3c9312f6139e`
- Tokenizer digest: `c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff`
- FA-v1 adapter SHA-256: `46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec`
- FA-v1 adapter-config SHA-256: `687100a0b6340b6096ca1e86066d3c13224b3c8e14ce9fb1b0cf78a52a8bdb7d`

## Preflight

The pre-execution static validation completed with status:

`P1C_STATIC_PREFLIGHT_OK`

The frozen implementation tests passed before primary execution:

- P1C metrics + phase scorer: `12 passed`
- P1C metrics + phase scorer + runner contract: `16 passed`
- runner syntax/import: `P1C_RUNNER_SYNTAX_IMPORT_OK`

No simulation state commit or model weight update was permitted.

## Primary result

The first preregistered gate was the mandatory equivalence check between:

1. ordinary exact BASE-only five-label teacher-forced scoring; and
2. `C00` BASE→BASE cached phase-split scoring.

Observed result:

- Status: `P1C_BASE_WRAPPER_EQUIVALENCE_FAIL`
- Comparisons: `800`
- Token IDs exact: `true`
- Maximum absolute total-log-probability difference: `0.21875`
- Maximum absolute mean-log-probability difference: `0.0703125`
- Frozen tolerance: `1e-5`
- Equivalence pass: `false`

Gate outcomes:

- `P1C-G0 = false`
- `P1C-G1 = NOT_EVALUABLE`
- `P1C-G2 = NOT_EVALUABLE`
- `P1C-G3 = NOT_EVALUABLE`
- `P1C-G4 = NOT_EVALUABLE`
- `P1C-G5 = NOT_EVALUABLE`

Primary result digest:

`e38870bbf1b0232987be9a73dabd8955148f4521c2c56f78ece931557b214065`

## Scientific interpretation

P1C did **not** test the preregistered phase-attribution contrasts to completion because the required measurement-equivalence premise failed first. Therefore this result does **not** establish that foundation→policy decoupling fails, succeeds, preserves structural signal, or localizes WAIT amplification to either phase.

The valid conclusion is narrower: under the frozen BF16 runtime and implementation, the ordinary BASE-only scorer and the cached split BASE→BASE path were not numerically equivalent within the preregistered `1e-5` tolerance, despite exact action-label token IDs. Because that equivalence was a mandatory G0 condition, all downstream mechanistic attribution gates are non-evaluable.

The observed score drift must not be retrospectively accepted by relaxing the tolerance. Any causal diagnosis of the drift belongs to a separately versioned post-hoc diagnostic study. Candidate mechanisms include, but are not limited to, full-sequence versus cached split-forward numerical differences, PEFT-disabled wrapper versus bare BASE behavior, and BF16 execution-path effects. These are hypotheses only and are not conclusions of P1C.

Founder Freeze remains **NOT_ESTABLISHED**.

## Frozen evidence hashes

Primary evidence root:

`/workspace/alifelm/evidence/WORLD_P1C_FOUNDATION_POLICY_PHASE_ABLATION_V1_F2E9E4D`

Primary summary SHA-256:

`47e9cbf2962bdbb6c3f59e4ae70fcc71bc204fbcb86a7e54bf1420085e492ee2`

Primary stdout SHA-256:

`188688bc311198b4e6028973a578c33ef27ed310951439ca05632a479db56867`

Canonical archive:

`/workspace/WORLD_P1C_FOUNDATION_POLICY_PHASE_ABLATION_V1_F2E9E4D_CANONICAL.tar.gz`

Canonical archive SHA-256:

`90eef02128d2caad16ef736170b28e1f8be76cb1331a53a2edb9e4d69bdff39d`

Archive round-trip verification: **PASS** (`P1C_CANONICAL_ARCHIVE_VERIFIED`).

Windows physical backup:

`E:\WORLD\BACKUP\p1c\WORLD_P1C_FOUNDATION_POLICY_PHASE_ABLATION_V1_F2E9E4D_CANONICAL.tar.gz`

Windows SHA-256 verification: **PASS**, exact match to the canonical archive SHA above.

## Preservation rule

The canonical primary evidence and archive above are immutable. Post-hoc diagnostics must write to a separate evidence root, use a separate study/version identifier, and must not overwrite or reinterpret this primary result as a successful P1C gate evaluation.
