# WORLD P1C-D1 Equivalence Localization V1

Status: POST-HOC DIAGNOSTIC PROTOCOL FROZEN BEFORE D1 MODEL FORWARD

Study ID: `WORLD_P1C_D1_EQUIVALENCE_LOCALIZATION_V1`

## 1. Purpose

P1C primary ended with `P1C_BASE_WRAPPER_EQUIVALENCE_FAIL` before phase-attribution gates were evaluated. This diagnostic localizes the source of the observed numerical disagreement. It does **not** reopen, repair, reinterpret, or rerun P1C primary, and it cannot retroactively make P1C G0 pass.

Frozen P1C facts motivating D1:

- P1C primary git commit: `f2e9e4dc9e7cdee6034ff33c663ffe434fa7c6ae`
- P1C results freeze commit: `274a51ed5f93805a6cbf41f1c757666cedf3cca1`
- P1C config SHA-256: `1ee7e53e8e8efd67e9868702138e89bf2532e737fa41329ad276c8a10ef98589`
- P1C primary result digest: `e38870bbf1b0232987be9a73dabd8955148f4521c2c56f78ece931557b214065`
- P1C summary SHA-256: `47e9cbf2962bdbb6c3f59e4ae70fcc71bc204fbcb86a7e54bf1420085e492ee2`
- P1C stdout SHA-256: `188688bc311198b4e6028973a578c33ef27ed310951439ca05632a479db56867`
- P1C canonical archive SHA-256: `90eef02128d2caad16ef736170b28e1f8be76cb1331a53a2edb9e4d69bdff39d`
- Windows physical backup hash verified equal to canonical archive.
- P1C observed wrapper-equivalence maximum absolute total-logP difference: `0.21875`
- P1C observed wrapper-equivalence maximum absolute mean-logP difference: `0.0703125`
- P1C token IDs were exact across all 800 label comparisons.

The P1C preregistered tolerance remains `1e-5` and is not modified.

## 2. Scientific question

Which execution component explains the P1C C00-versus-ordinary-BASE discrepancy?

D1 decomposes three candidate sources:

1. full-sequence scoring versus cached split-prefill scoring;
2. bare Transformers BASE versus PEFT-wrapped BASE with adapter disabled;
3. BF16 numerical execution versus FP32 execution for the bare full-versus-cached contrast.

No claim is made in advance that any one source must dominate.

## 3. Frozen identities

D1 uses the exact accepted P1C/P1B identities:

- base model: `allenai/OLMo-2-0425-1B-Instruct`
- base revision: `48d788eca847d4d7548f375ad03d3c9312f6139e`
- base checkpoint SHA-256: `36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f`
- tokenizer digest: `c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff`
- FA-v1 adapter SHA-256: `46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec`
- FA-v1 adapter config SHA-256: `687100a0b6340b6096ca1e86066d3c13224b3c8e14ce9fb1b0cf78a52a8bdb7d`
- canonical pip-freeze SHA-256: `a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf`
- runtime package count: 60

No weights are updated.

## 4. Cohorts

### D1-BF16 cohort

Reuse the exact P1C held-out R3 cohort only as a post-hoc diagnostic denominator:

- case indices: `2000..2031`
- 32 matched case sets
- five context classes in frozen order:
  - `QUIET`
  - `MESSAGE_RECEIVED`
  - `PROPOSAL_RECEIVED`
  - `OWN_PROPOSAL_PENDING`
  - `RECENT_INTERACTION`
- 160 canonical WORLD contexts total.

The exact canonical rendered WORLD-context bytes must be identical across every D1 condition.

### D1-FP32 subset

Use the deterministic subset `2000..2003` across all five context classes:

- 4 matched case sets
- 20 contexts total.

This subset is fixed before D1 inference and exists only to measure precision-path attenuation or persistence.

## 5. Frozen action-label scorer

Use the exact five labels and exact P1C/P1B selector prefix:

```text
\nAction selection JSON:\n{"action_label":"
```

Labels, in frozen order:

1. `NO_DIRECTED_ACTION`
2. `DIRECT_TEXT`
3. `OPEN_BILATERAL_REQUEST`
4. `CONFIRM_BILATERAL_REQUEST`
5. `DECLINE_BILATERAL_REQUEST`

Record for every score set:

- context token IDs;
- selector-prefix token IDs;
- candidate-label token IDs;
- total log probability;
- mean log probability;
- full rank.

Tokenization must be byte/token aligned under the same fail-closed rule used by P1C.

## 6. BF16 execution conditions

For all 160 contexts, measure exactly four paths:

### E0 — BARE_FULL_BF16

Separately loaded exact bare BASE model, BF16, ordinary full-sequence five-label scorer.

### E1 — BARE_CACHED_BF16

The same separately loaded exact bare BASE model, BF16, cached phase scorer at the frozen P1C boundary. No adapter wrapper exists. WORLD context is prefetched exactly once and reused through `past_key_values` without recomputing the WORLD context.

### E2 — PEFT_DISABLED_FULL_BF16

Exact FA-v1 PEFT runtime, BF16, adapter disabled for the entire ordinary full-sequence five-label scorer.

### E3 — PEFT_DISABLED_CACHED_BF16

Exact FA-v1 PEFT runtime, BF16, adapter disabled for both WORLD-context prefill and selector/scoring continuation using the exact cached phase scorer. This is the operational P1C C00 path.

No FA-enabled scoring is performed in D1.

## 7. FP32 precision diagnostic

For the frozen 20-context subset, load a separate exact bare BASE runtime in FP32 and measure:

- `F0 — BARE_FULL_FP32`
- `F1 — BARE_CACHED_FP32`

The model checkpoint bytes and tokenizer bytes remain unchanged; only inference dtype differs.

FP32 is diagnostic only and does not replace the canonical BF16 runtime.

## 8. Predefined contrasts

For every label/context pair, compute absolute differences in total and mean log probability.

### Cache-path effect on bare BASE

`CACHE_BARE_BF16 = E1 - E0`

### PEFT-wrapper effect under full scoring

`WRAPPER_FULL_BF16 = E2 - E0`

### PEFT-wrapper effect under cached scoring

`WRAPPER_CACHED_BF16 = E3 - E1`

### Cache-path effect inside PEFT-disabled runtime

`CACHE_PEFT_DISABLED_BF16 = E3 - E2`

### Original P1C discrepancy reconstruction

`P1C_RECONSTRUCTED = E3 - E0`

The recorded D1 maximum absolute `P1C_RECONSTRUCTED` total and mean differences must equal the P1C primary reported maxima (`0.21875`, `0.0703125`) exactly under the same frozen numeric representation. If not, D1 status is `PRIMARY_RECONSTRUCTION_MISMATCH` and attribution is not interpreted.

### Precision contrast

On the fixed 20-context subset:

- `CACHE_BARE_BF16_SUBSET = E1 - E0`
- `CACHE_BARE_FP32_SUBSET = F1 - F0`

Report the max, median, mean, and nonzero fraction of absolute total- and mean-logP differences for both dtypes.

No post-hoc tolerance is used to declare P1C equivalent.

## 9. Integrity requirements

D1 integrity requires all of the following:

- exact frozen model/tokenizer/adapter/runtime identities;
- exact P1C cohort and fixed FP32 subset;
- 160/160 canonical rendered inputs byte-identical across E0-E3;
- 20/20 canonical rendered inputs byte-identical across F0-F1 and corresponding BF16 subset;
- exact candidate-label token IDs across all compared paths;
- exactly 160 score sets for each E0/E1/E2/E3;
- exactly 20 score sets for each F0/F1;
- first score set of each path repeated once with exact serialized numeric equality;
- no state commits;
- no model weight updates;
- no generation, retries, fallback, repair, EOS manipulation, scalar calibration, or action hints;
- immutable digested evidence output;
- original P1C evidence directory and canonical archive remain untouched.

If the original P1C reconstruction fails, source localization is `NOT_INTERPRETABLE`.

## 10. Interpretation rules

D1 is descriptive/mechanistic, not a new behavioral admission gate.

Interpret only the measured component magnitudes:

- If `CACHE_BARE_BF16` is materially nonzero while `WRAPPER_FULL_BF16` is near numeric zero, the ordinary-vs-cached execution path is implicated independently of PEFT wrapping.
- If `WRAPPER_FULL_BF16` or `WRAPPER_CACHED_BF16` is materially nonzero, PEFT wrapping contributes an additional execution difference even with the adapter disabled.
- If the FP32 bare cache contrast is substantially smaller than the matched BF16 contrast, BF16 numerical execution contributes to the cache-path discrepancy.
- If FP32 retains a comparable cache discrepancy, the split execution path itself remains implicated beyond BF16 rounding alone.

The words `materially`, `substantially`, and `comparable` are narrative descriptions only. D1 reports raw magnitudes and does not define a new scientific pass threshold from them.

D1 cannot establish context-sensitive policy competence, autonomous behavior, Foundation neutrality, deployment suitability, or Founder Freeze.

## 11. Preservation

D1 outputs must use a new evidence root and a new canonical archive. P1C primary evidence must never be modified or supplemented in place.

Founder Freeze remains `NOT_ESTABLISHED`.
