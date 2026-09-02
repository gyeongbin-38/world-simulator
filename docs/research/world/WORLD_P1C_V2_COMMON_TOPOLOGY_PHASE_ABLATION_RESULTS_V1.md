# WORLD P1C-v2 Common-Topology Foundation–Policy Phase Ablation Results V1

Status: RESULTS FROZEN

Study ID: `WORLD_P1C_V2_COMMON_TOPOLOGY_PHASE_ABLATION_V1`

## 1. Scope

This document freezes the primary P1C-v2 common-topology phase-ablation result. P1C-v2 was preregistered after P1C-v1 failed its mandatory full-versus-cached BASE equivalence control and the separate D1 diagnostic localized that failure to the BF16 full-versus-cached execution topology.

P1C-v2 therefore compared all causal phase conditions under one common cached split-prefill topology and used a fresh held-out deterministic R3 cohort (`3000..3031`, 32 matched cases x 5 context classes = 160 contexts).

P1C-v2 is a mechanistic study. It does not establish autonomous policy competence, behavioral admission, deployment suitability, or Founder Freeze.

## 2. Frozen identities

- execution commit: `4fcbf4827a2887700dc59e180a7c08e5117b59b9`
- preregistration commit: `9d6e7831c54c5aea3cb23f61c4dc26b5a2668a6f`
- frozen config SHA-256: `0720b5c7d02a86580938c060faaab0c6f127ca5043c96cfdff5881bc9dc02c99`
- canonical runtime pip-freeze SHA-256: `a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf`
- runtime package count: `60`
- base checkpoint SHA-256: `36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f`
- FA-v1 adapter SHA-256: `46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec`
- FA-v1 adapter config SHA-256: `687100a0b6340b6096ca1e86066d3c13224b3c8e14ce9fb1b0cf78a52a8bdb7d`

## 3. Primary execution outcome

- status: `P1C_V2_MEASUREMENT_COMPLETE`
- localization: `INTERPRETABLE`
- result digest: `0e19ae757ee07121102e1bd278125fe41d92e55b30add75f1e5895a1c315df04`
- G0: PASS
- G1: PASS
- G2: FAIL
- G3: PASS
- G4: PASS
- G5: `C00 FAIL`, `C01 FAIL`, `C10 PASS`, `C11 FAIL`

No generation, model-weight update, simulation-state commit, retry, fallback, repair, EOS manipulation, scalar calibration, or action hint was used.

## 4. G0 — common-topology integrity

The cached-wrapper parity control passed exactly across all 800 label comparisons:

- rendered WORLD bytes exact: `true`
- context token IDs exact: `true`
- selector-prefix token IDs exact: `true`
- combined token IDs exact: `true`
- candidate-label token IDs exact: `true`
- total log probability exact: `true`
- mean log probability exact: `true`
- full rank exact: `true`
- post-hoc tolerance: `null`

Thus, unlike P1C-v1, phase attribution in P1C-v2 is interpretable under the preregistered common cached execution topology.

## 5. G1 — decode-side WAIT induction: PASS

Contrast: `M_C01 - M_C00`.

- count: `160`
- median: `+1.5263671875`
- positive count: `160/160`
- positive fraction: `1.0`
- preregistered minimum positive fraction: `0.75`

Interpretation:

FA-v1 activation during selector/scoring continuation is sufficient to increase the WAIT margin consistently even when WORLD context was encoded by BASE.

## 6. G2 — prefill-side WAIT induction: FAIL

Contrast: `M_C10 - M_C00`.

- count: `160`
- median: `+0.21484375`
- positive count: `113/160`
- positive fraction: `0.70625`
- preregistered minimum positive fraction: `0.75`

The median is positive, but the preregistered positive-fraction criterion is not met. Therefore consistent prefill-only WAIT induction is not established.

This FAIL must not be interpreted as prefill neutrality. It means only that the frozen sufficiency gate did not pass.

## 7. G3 — structural replication and carryover: PASS

### 7.1 Full-adapter structural gain, C11 versus C00

All three structural contrasts replicated:

- `S_msg`: median `+0.25390625`, `31/32` positive, fraction `0.96875`, PASS
- `S_owner`: median `+0.4921875`, `32/32` positive, fraction `1.0`, PASS
- `S_prop`: median `+0.30859375`, `32/32` positive, fraction `1.0`, PASS

### 7.2 Prefill-only structural carryover, C10 versus C00

- `S_msg`: median `+0.05419921875`, `22/32` positive, fraction `0.6875`, FAIL
- `S_owner`: median `+0.5048828125`, `32/32` positive, fraction `1.0`, PASS
- `S_prop`: median `+0.47265625`, `32/32` positive, fraction `1.0`, PASS

The preregistration required at least two of three contrasts to pass both full-adapter replication and prefill-only carryover on the same contrast. `S_owner` and `S_prop` satisfy this condition; therefore G3 PASSes.

Interpretation:

FA-v1 adds proposal/ownership-related action-structural information during WORLD-context prefill that remains measurable when subsequent selector/scoring continuation is BASE-only. Message-specific carryover was positive in median but did not meet the preregistered consistency threshold.

## 8. G4 — phase-decoupling candidate: PASS

Contrast: `M_C11 - M_C10`.

- count: `160`
- median: `+3.159423828125`
- positive count: `160/160`
- positive fraction: `1.0`

Because G3 also passed, P1C-v2 satisfies the frozen decoupling-candidate gate.

Bounded interpretation:

Under one common cached execution topology, `FA→BASE` preserves replicated `S_owner` and `S_prop` structural gain while reducing the WAIT margin relative to `FA→FA` in every tested context.

This is evidence for a separately versioned phase-decoupled runtime architecture experiment; it is not deployment authorization.

## 9. G5 — latent rank-1 context sensitivity

### C00 — BASE→BASE: FAIL

- matched sensitive: `20/32`
- matched sensitivity rate: `0.625`
- TVD versus QUIET:
  - MESSAGE_RECEIVED: `0.625`
  - OWN_PROPOSAL_PENDING: `0.0`
  - PROPOSAL_RECEIVED: `0.0`
  - RECENT_INTERACTION: `0.0`
- TVD-passing classes: `1/4`

C00 fails because at least two non-QUIET TVDs were required.

### C01 — BASE→FA: FAIL

- matched sensitive: `0/32`
- matched sensitivity rate: `0.0`
- all non-QUIET TVDs: `0.0`

### C10 — FA→BASE: PASS

- matched sensitive: `15/32`
- matched sensitivity rate: `0.46875`
- TVD versus QUIET:
  - MESSAGE_RECEIVED: `0.4375`
  - OWN_PROPOSAL_PENDING: `0.40625`
  - PROPOSAL_RECEIVED: `0.4375`
  - RECENT_INTERACTION: `0.4375`
- TVD-passing classes: `4/4`

C10 is the only phase condition that passes the frozen latent rank-1 context-sensitivity diagnostic.

### C11 — FA→FA: FAIL

- matched sensitive: `0/32`
- matched sensitivity rate: `0.0`
- all non-QUIET TVDs: `0.0`

G5 remains diagnostic only and does not establish autonomous policy competence.

## 10. Factorial interaction diagnostics

These diagnostics had no pass/fail thresholds.

### 10.1 WAIT interaction

`I_wait = M_C11 - M_C10 - M_C01 + M_C00`

- count: `160`
- median: `+1.547607421875`
- mean: `+1.4939666748046876`
- positive fraction: `1.0`
- negative fraction: `0.0`
- zero fraction: `0.0`

Interpretation:

Prefill and selector/scoring adapter activation interact positively for WAIT margin. The full FA→FA WAIT effect is therefore not well described as a simple additive sum of isolated phase effects.

### 10.2 Structural interactions

`S_msg` interaction:

- median: `-0.197265625`
- mean: `-0.1895751953125`
- negative fraction: `1.0`

`S_prop` interaction:

- median: `+0.4150390625`
- mean: `+0.44122314453125`
- positive fraction: `1.0`

`S_owner` interaction:

- median: `+0.0634765625`
- mean: `+0.075439453125`
- positive fraction: `0.625`
- negative fraction: `0.375`

These interactions show that adapter phase effects are structure-specific rather than a single scalar transformation.

## 11. Scientific interpretation

The frozen P1C-v2 result supports the following bounded conclusions:

1. The P1C-v1 numerical confound was successfully avoided by comparing all causal conditions under one cached execution topology.
2. FA-v1 selector/scoring activation is sufficient for strong and fully consistent WAIT-margin induction (`G1 PASS`).
3. FA-v1 prefill alone does not meet the frozen consistency threshold for WAIT induction (`G2 FAIL`), although a positive effect is present in 113/160 contexts and the median is positive.
4. Full FA-v1 structural gains replicate on all three preregistered contrasts on the fresh cohort.
5. `FA→BASE` preserves robust `S_owner` and `S_prop` structural gains while `S_msg` carryover does not meet the frozen consistency threshold.
6. `FA→BASE` reduces WAIT margin relative to `FA→FA` in 160/160 contexts with median reduction `3.159423828125` log-probability units (`G4 PASS`).
7. `FA→BASE` is the only tested phase condition that passes the preregistered latent rank-1 context-sensitivity diagnostic.
8. WAIT has a strictly positive factorial interaction in all 160 contexts, so the full-adapter WAIT effect is phase-interactive rather than a simple constant decode-only bias.
9. The structural interaction is not uniform: message specificity shows negative interaction, proposal specificity positive interaction, and ownership a weaker mixed positive interaction.

The strongest architecture candidate supported by this evidence is therefore a phase-decoupled design:

`WORLD observation -> FA-v1 context grounding/prefill -> adapter OFF -> BASE policy scoring -> ActionIntent -> deterministic validation/commit`

This candidate should be tested in a separately preregistered runtime/behavioral study. P1C-v2 does not establish that BASE is an adequate autonomous selector, that FA-v1 is globally policy-neutral, or that the candidate should be deployed.

## 12. Preservation

Frozen primary evidence:

- `summary.json` SHA-256: `8632473c2e13983d535a8b16381b3f8e4dc1eea68741ccb0ad2e9cfd4ef1c40a`
- `details.json` SHA-256: `c03e4370cf077c0c7c492727375141ecb66623762bcc96b0881ae147c5a272ea`
- stdout SHA-256: `061d50db2eb7dec80af44c251bf5586c13df64f1a8a486e530ab693a7800e004`
- canonical archive: `WORLD_P1C_V2_COMMON_TOPOLOGY_PHASE_ABLATION_V1_4FCBF48_CANONICAL.tar.gz`
- canonical archive SHA-256: `b34f60b98868bf9a26b3d726fb4b6fd9093e9d2ec462b247cb82553900b0c39d`
- canonical archive round-trip verification: `P1C_V2_CANONICAL_ARCHIVE_VERIFIED`

The canonical archive was created before any post-hoc follow-up inference. The numerical inspection used for this results document read the frozen `summary.json` only and did not alter primary evidence.

## 13. Admission status

P1C-v2 does not establish:

- autonomous policy competence;
- behavioral validity;
- Foundation neutrality as a deployed selector;
- deployment suitability;
- Founder Freeze.

Founder Freeze remains `NOT_ESTABLISHED`.
