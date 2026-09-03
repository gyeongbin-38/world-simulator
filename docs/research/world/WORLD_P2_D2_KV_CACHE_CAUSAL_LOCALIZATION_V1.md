# WORLD P2-D2 — KV-Cache Causal Localization V1

Status: **PREREGISTERED MECHANISTIC DIAGNOSTIC**

## 1. Scientific question

P2-D1 established a deterministic regime switch while the selector adapter was held BASE:

- C00, BASE WORLD-prefill -> BASE selector: SEND rank-1 in 160/160 contexts.
- C10, FA WORLD-prefill -> BASE selector: WAIT rank-1 in 160/160 contexts.
- Total and mean rank-1 agree exactly.
- Context-dependent action-score movement remains under C10.

P2-D2 asks a narrower causal question:

> Which transformer-layer WORLD-prefill KV caches mediate the C00 SEND -> C10 WAIT decision-regime switch observed by the fixed BASE selector?

This study does not reopen P2 admission and does not modify weights, ActionIntent generation, simulation state, decoding policy, action schemas, or the frozen D1 result.

## 2. Why cache patching is the primary intervention

In the frozen P2-D1 topology, WORLD context is forwarded once in Phase A. The BASE selector suffix is then forwarded using only the retained Phase-A `past_key_values`. Phase-A logits are not used as selector input. Therefore the retained WORLD-prefill cache is the direct computational channel through which the C00/C10 prefill intervention reaches the fixed BASE selector.

D2 intervenes on that channel directly: for selected transformer layers, both key and value cache tensors from a donor prefill are transplanted into a cloned target prefill cache before the unchanged BASE selector suffix is evaluated.

No hidden-state hook, residual-stream replacement, attention-head ablation, MLP ablation, parameter modification, context recomputation after the patch, calibration, retry, repair, or fallback is allowed in V1.

## 3. Frozen source evidence

D2 is downstream of the canonical P2-D1 R2 result:

- D1 study: `WORLD_P2_D1_DECISION_BOUNDARY_LOCALIZATION_V1`
- D1 scientific implementation commit: `5f7f5e02a66c253e0352771cbb35f0db6c408072`
- D1 result digest: `865616cdb65e5f4c969a9302c02bb285167db06a905e1497b05e4e0912935c20`
- D1 details SHA-256: `0e5e62709d58168c9922645c1d05d54a7f5c417b68b3f461b4558d3706ca3b17`
- D1 canonical archive SHA-256: `c42999e001c789a4a43fa14962119315066b2df6c66e3b472ce76a6f27cad2f1`
- frozen P2 interpretation remains: `C10_NOT_BEHAVIORALLY_ADMITTED`

The D2 runner must verify source D1 summary/details/stdout/archive identity before any scientific measurement and again after the final measurement.

## 4. Frozen model/cache identity

The accepted model is the same immutable OLMo-2-0425-1B-Instruct BF16 deployment used by D1.

D2 requires:

- exactly 16 transformer cache layers,
- identical C00/C10 tokenized WORLD-context IDs for every matched case,
- equal cache sequence length, tensor shape, dtype, and device at every layer,
- both key and value tensors patched together,
- BASE selector state for every D2 selector continuation,
- no WORLD-context recomputation after a hybrid cache has been constructed.

If the live cache representation cannot be uniquely mapped to 16 ordered layer K/V pairs, the run fails closed before scientific localization.

## 5. Frozen cohort

Context classes, case identities, rendered bytes, and tokenizer IDs are inherited from canonical D1.

Full cohort:

- `QUIET`
- `MESSAGE_RECEIVED`
- `PROPOSAL_RECEIVED`
- `OWN_PROPOSAL_PENDING`
- `RECENT_INTERACTION`
- case indices 4000..4031 inclusive
- 32 cases per class
- 160 total contexts

Screening cohort for Stages A and B:

- same five context classes
- case indices 4000..4003 inclusive
- 4 cases per class
- 20 total contexts

No screening case may be substituted after preregistration.

## 6. Cache conditions

For each context, compute exactly two source WORLD-prefill caches:

- `B`: BASE prefill cache, equivalent to D1 C00 Phase A.
- `F`: FA prefill cache, equivalent to D1 C10 Phase A.

The selector is always BASE.

For a selected layer set `L`:

### Rescue patch

`F[B@L]`: start from a deep clone of F and replace both K and V at every layer in L with clones from B.

Question: does BASE-derived cache information rescue the C10 WAIT regime toward SEND?

### Induction patch

`B[F@L]`: start from a deep clone of B and replace both K and V at every layer in L with clones from F.

Question: does FA-derived cache information induce the C10 WAIT regime inside the C00 SEND baseline?

All unselected layers remain exactly from the target cache.

## 7. Decision readout

D1 established SEND and WAIT as the universal top two actions in opposite order, with identical two-token branch counts in both canonical baselines. D2 therefore uses the preregistered D1 SEND/WAIT axis as the primary mediator readout.

For every evaluated condition define:

`G = total_log_probability(WAIT) - total_log_probability(SEND)`

Thus:

- `G < 0`: SEND side of the D1 boundary.
- `G > 0`: WAIT side of the D1 boundary.

The screening scorer must preserve D1's exact action-branch decision point: all five frozen forced-action schemas participate in common-prefix legal-set synchronization and divergence detection. Stages A/B may persist only WAIT and SEND branch continuations after that same five-schema divergence point. Stage C scores and stores all five actions.

No new token-length correction is introduced. WAIT and SEND are both exactly two scored branch tokens in canonical D1. Mean-log-probability is recorded as a secondary identity check.

## 8. Per-case causal mediator quantities

For each case:

- `G_B`: unpatched BASE-prefill/BASE-selector gap.
- `G_F`: unpatched FA-prefill/BASE-selector gap.
- `D = G_F - G_B`.

D2 requires `D > 0` for every screening and confirmation case, consistent with canonical D1; otherwise source identity fails closed.

For layer set L:

- rescue gap: `G_R(L) = G(F[B@L])`
- induction gap: `G_I(L) = G(B[F@L])`
- normalized rescue fraction: `NR(L) = (G_F - G_R(L)) / D`
- normalized induction fraction: `NI(L) = (G_I(L) - G_B) / D`
- symmetric mediator score: `S(L) = (NR(L) + NI(L)) / 2`

Fractions are descriptive and are not clipped to [0,1]. Overshoot and negative mediation are preserved.

Also record:

- rescue sign flip: `G_R(L) < 0`
- induction sign flip: `G_I(L) > 0`
- raw WAIT and SEND total/mean scores
- selector-prefix and branch forward counts
- cache-layer shapes and patch layer IDs

## 9. Stage 0 — implementation-positive controls

Before layer localization is admitted, the screening cohort must pass:

1. Unpatched B and F readouts reproduce source D1 SEND/WAIT scores/ranks for the same cases.
2. An all-layer rescue patch `F[B@0..15]` reproduces the B selector readout exactly.
3. An all-layer induction patch `B[F@0..15]` reproduces the F selector readout exactly.
4. Self-donor patches are exact no-ops in unit/contract tests.
5. Cache transplantation never mutates donor or source target caches.

Any failure is implementation/runtime evidence, not a scientific D2 result.

## 10. Stage A — coarse 4-block localization

Frozen layer blocks:

- `Q0 = [0,1,2,3]`
- `Q1 = [4,5,6,7]`
- `Q2 = [8,9,10,11]`
- `Q3 = [12,13,14,15]`

Evaluate rescue and induction for every block on all 20 screening contexts.

For each block compute the median of per-case `S(L)` over the 20 screening contexts.

Advancement rule:

- rank blocks by descending median symmetric mediator score;
- ties are resolved by lower starting layer index;
- advance exactly the top two blocks.

No magnitude threshold may be introduced after observing Stage-A results.

## 11. Stage B — individual-layer localization

Evaluate every individual layer contained in the two Stage-A winning blocks on the same frozen 20-context screening cohort, in both rescue and induction directions.

For each layer compute median per-case `S({layer})`.

Advancement rule:

- rank candidate layers by descending median symmetric mediator score;
- ties are resolved by lower layer index;
- advance exactly the top two individual layers, `L1` and `L2`.

No layer outside the two Stage-A winning blocks may be added post hoc in V1.

## 12. Stage C — full-cohort confirmation

On all 160 frozen contexts, evaluate and store full five-action D1-compatible branch scores for:

- unpatched B baseline,
- unpatched F baseline,
- rescue at `{L1}`,
- induction at `{L1}`,
- rescue at `{L2}`,
- induction at `{L2}`,
- rescue at `{L1,L2}`,
- induction at `{L1,L2}`.

Primary confirmation report:

- full distribution of `G`, `NR`, `NI`, and `S` by context class and overall,
- rescue sign-flip count out of 160,
- induction sign-flip count out of 160,
- five-action total-rank-1 distribution for every Stage-C condition,
- whether any third action overtakes both WAIT and SEND,
- per-context-class paired summaries.

No new binary admission threshold is introduced. Exact counts and continuous effects are the scientific result.

### Exact repeat

The two-layer union rescue and two-layer union induction conditions are repeated in full over all 160 contexts. Stored scientific records for each repeated condition must be serialization-identical for integrity admission. Numerical deltas are also reported.

## 13. Descriptive localization labels

Labels are secondary summaries only:

- `UNION_BIDIRECTIONAL_UNIVERSAL_FLIP`: union rescue flips all 160 cases to `G < 0` and union induction flips all 160 cases to `G > 0`.
- `UNION_BIDIRECTIONAL_NONUNIVERSAL`: both directions contain at least one sign flip but universality is not reached.
- `UNION_ONE_DIRECTION_ONLY`: sign flips occur in only one intervention direction.
- `NO_SIGN_FLIP_MEDIATION`: neither union direction produces a sign flip.

Continuous mediator effects and exact counts remain primary; these labels do not alter P2 or D1.

## 14. Integrity and fail-closed requirements

The run is scientifically interpretable only if all hold:

- repository HEAD descends from this preregistration commit;
- this protocol and its config are byte-identical to preregistration;
- D1 source evidence hashes and result identity match before and after D2;
- canonical runtime pip-freeze identity matches D1;
- base model/tokenizer/adapter identities match frozen deployment;
- 16-layer cache mapping is unique and shape-compatible;
- Stage-0 all-layer controls pass exactly;
- screening/advancement follows the frozen rules;
- Stage-C union exact repeats are serialization-identical;
- no retries, repairs, fallbacks, ActionIntent generation, simulation-state commits, or weight updates occur.

A failure before complete integrity-admitted measurement is implementation/infrastructure evidence only. Failed output roots and stdout logs are immutable; fixes must be protocol-neutral and use a new versioned attempt.

## 15. Interpretation boundary

A positive layer-cache mediation result would establish causal mediation through selected WORLD-prefill KV-cache layers in this frozen model/runtime/task. It would not by itself establish a human-level concept of agency, a unique residual-stream mechanism, a specific attention head, or generalization beyond the frozen WORLD cohort.

Further head-, token-, or residual-level localization requires a separately preregistered follow-up.