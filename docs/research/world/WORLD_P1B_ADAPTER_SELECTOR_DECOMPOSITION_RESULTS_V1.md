# WORLD P1B Adapter–Selector Decomposition Results V1

Status: PRIMARY RESULTS FROZEN AFTER EXECUTION

## 1. Study identity

- Study: `WORLD_P1B_ADAPTER_SELECTOR_DECOMPOSITION_V1`
- Preregistration commit: `13634bc13122f8b194a4bdba0e6feadee0f0e54d`
- Frozen config head before implementation: `e73ccfaa34c379610cbfaddda6536cb562b35ae8`
- Executed runner commit: `e02f3f6b7165797cb02c383b097610c962c1fc99`
- Result digest: `cacda0ea12dbabd85c1c8a2dd743ef89ac5738b13f8cbbe0f1a9ff5e2a211111`
- Summary SHA-256: `114c8a894edf80ba5d2dfd4c6b64239ca4d621aa603142bc108976be5416d2b1`
- Stdout SHA-256: `11106dd00171305c7ac6787c140969f67ad701d7ce706d3930282013dcf27bb3`
- Canonical archive SHA-256: `87d815436254d2ed4eafeeeb49fb1d03edd5ccac3dc9949753c2b46dfcd51e6a`
- Canonical archive round-trip: `P1B_CANONICAL_ARCHIVE_VERIFIED`

## 2. Runtime/deployment identity

P1B executed under the frozen canonical WORLD runtime:

- Python 3.12.3
- torch 2.7.1+cu118
- transformers 5.16.1
- peft 0.20.0
- lm-format-enforcer 0.11.3
- NVIDIA A40, compute capability 8.6
- exact pip-freeze SHA-256: `a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf`
- package count: 60

Base model and tokenizer identities matched the preregistration. FA-v1 adapter SHA-256 matched `46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec`; adapter config SHA-256 matched `687100a0b6340b6096ca1e86066d3c13224b3c8e14ce9fb1b0cf78a52a8bdb7d`.

## 3. Integrity result

`P1B-G0 = PASS`.

The held-out BASE_ONLY and FA_V1 rendered inputs were byte-identical for all 160 contexts before researcher-only measurement suffixes. All preregistered teacher-forced score sets and label-only generations completed. Exact-repeat checks passed. Runtime parameters remained frozen. Simulation state commits = 0. Weight updates = 0.

P1B is therefore evaluable under the frozen interpretation matrix.

## 4. Gate results

- `P1B-G1 = PASS`
- `P1B-G2 = PASS`
- `P1B-G3 = FAIL`
- `P1B-G4 = PASS`
- `P1B-G5(BASE_ONLY) = FAIL`
- `P1B-G5(FA_V1) = FAIL`

These gates are mechanistic diagnostics, not WORLD behavioral admission gates.

## 5. G1 — payload-free interface diagnostic

On the archived-P1 paired cohort, FA-v1 under the payload-free label-only selector produced `NO_DIRECTED_ACTION` in all 80 contexts:

- QUIET: 16/16 WAIT
- MESSAGE_RECEIVED: 16/16 WAIT
- PROPOSAL_RECEIVED: 16/16 WAIT
- OWN_PROPOSAL_PENDING: 16/16 WAIT
- RECENT_INTERACTION: 16/16 WAIT

Formal interpretation: typed action-payload serialization is not necessary to produce the tested FA-v1 WAIT-dominant selector behavior. This does not establish that I3 has zero effect.

## 6. G2 — adapter WAIT-margin amplification

Across all 160 held-out matched contexts, FA-v1 increased the teacher-forced WAIT margin relative to BASE_ONLY:

- positive count: 160/160
- positive fraction: 1.0
- median `A_wait`: `3.52783203125`
- preregistered threshold: median > 0 and positive fraction >= 0.75

`P1B-G2 = PASS`.

Formal interpretation: FA-v1 consistently amplifies the total-log-probability separation of `NO_DIRECTED_ACTION` from the best directed label relative to the exact base model under the tested scoring interface.

This is an adapter effect under the frozen measurement; it must not be rewritten as a claim that a constant WAIT bias alone explains all behavior.

## 7. G3 — absolute FA-v1 structural selectivity

Held-out FA-v1 action-structure contrasts:

### S_msg

- median: `0.015625`
- positive: 17/32 = 0.53125
- result: FAIL

### S_prop

- median: `0.05078125`
- positive: 22/32 = 0.6875
- result: FAIL

### S_owner

- median: `0.31640625`
- positive: 32/32 = 1.0
- result: PASS

P1B-G3 required at least two of three contrasts to pass. Therefore `P1B-G3 = FAIL`.

Formal interpretation: P1B does not establish sufficiently broad absolute action-structure-aligned latent discrimination for FA-v1 under the preregistered G3 threshold. Proposal direction/ownership structure is strongly present; message and proposal-response specificity remain below the frozen consistency threshold.

## 8. G4 — adapter structural gain relative to BASE_ONLY

FA-v1 minus BASE_ONLY held-out structural gains:

### A_S_msg

- median: `0.158203125`
- positive: 27/32 = 0.84375
- result: PASS

### A_S_prop

- median: `0.34375`
- positive: 30/32 = 0.9375
- result: PASS

### A_S_owner

- median: `0.48828125`
- positive: 32/32 = 1.0
- result: PASS

All three contrasts pass; `P1B-G4 = PASS`.

Formal interpretation: FA-v1 strengthens context/action-specific latent score structure relative to the exact base model on the held-out cohort, even though the absolute FA-v1 G3 threshold is not met for two of three contrasts.

G3 FAIL and G4 PASS are not contradictory: the adapter can improve structural contrasts relative to BASE_ONLY without making every absolute contrast sufficiently positive and consistent under the preregistered G3 rule.

## 9. G5 — label-only generated context sensitivity

### BASE_ONLY

Held-out generated distribution:

- QUIET: DIRECT_TEXT 32/32
- MESSAGE_RECEIVED: DIRECT_TEXT 29/32, WAIT 3/32
- PROPOSAL_RECEIVED: DIRECT_TEXT 32/32
- OWN_PROPOSAL_PENDING: DIRECT_TEXT 29/32, WAIT 3/32
- RECENT_INTERACTION: DIRECT_TEXT 32/32

Matched sensitive case sets: 5/32 = 0.15625. No non-QUIET context reached TVD 0.25 versus QUIET. `P1B-G5(BASE_ONLY) = FAIL`.

### FA_V1

Every held-out context class produced WAIT 32/32. Matched sensitive case sets: 0/32. All TVDs versus QUIET = 0. `P1B-G5(FA_V1) = FAIL`.

Formal interpretation: neither exact BASE_ONLY nor FA-v1 establishes generated label-only context-sensitive selection under the P1B cohort. BASE_ONLY exhibits a strong DIRECT_TEXT attractor; FA-v1 exhibits a complete WAIT attractor in this held-out measurement.

## 10. Joint mechanistic interpretation

The preregistered joint result is:

- WAIT dominance persists after typed payload removal (G1 PASS).
- FA-v1 consistently increases WAIT margin relative to the base (G2 PASS).
- FA-v1 does not meet the broad absolute structural-selectivity threshold (G3 FAIL).
- FA-v1 nevertheless strengthens all three structural contrasts relative to BASE_ONLY (G4 PASS).
- Neither condition establishes generated context-sensitive selection (G5 FAIL for both).

The strongest supported mechanistic interpretation is therefore a two-effect adapter pattern:

1. FA-v1 adds measurable action-structure-aligned latent signal relative to BASE_ONLY.
2. FA-v1 simultaneously and consistently amplifies a global WAIT-oriented selector margin strongly enough that generated label-only behavior collapses to WAIT across the tested held-out cohort.

This does **not** establish that grounding is fully solved, that policy competence exists below the decision boundary, or that a scalar calibration correction would be scientifically valid. It does show that a pure "typed payload caused WAIT" explanation is inadequate, and that a pure "FA-v1 erased all structural context signal" explanation is also inadequate.

## 11. Architecture/research boundary after P1B

P1B does not authorize an implementation change. In particular, the following remain separate, future-versioned interventions rather than consequences of this result:

- subtracting a WAIT bias or residualizing scores;
- using FA-v1 only for grounding and switching it off for policy selection;
- introducing a separate policy head or selector model;
- replacing the base model;
- retraining FA-v1;
- changing the action interface or constraints.

Those are hypothesis-driven next experiments, not retroactive fixes to P1B.

## 12. Historical studies remain unchanged

P1B does not alter:

- A0: motor/interface validity established under I3; Founder Freeze not established.
- P0: infrastructure/causal/persistence/replay/completion-order integrity established; nontrivial policy competence not established.
- P1: G0 PASS, G1 FAIL, G2 FAIL; classification `NO_CONTEXT_SENSITIVE_POLICY_EVIDENCE`.

No P1B finding may retroactively change the above classifications.

## 13. Founder Freeze

Founder Freeze remains `NOT_ESTABLISHED`.

P1B is a mechanistic decomposition study and cannot establish behavioral admission or Founder Freeze by itself.
