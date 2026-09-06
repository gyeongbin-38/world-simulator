# WORLD P2-D4 — KV Component Decomposition V1

Status: **PREREGISTERED MECHANISTIC DIAGNOSTIC**

## 1. Scientific question

P2-D1 established a deterministic SEND -> WAIT decision-regime shift caused by the FA WORLD-prefill while the selector remained BASE. P2-D2 localized strong causal leverage to WORLD-prefill KV state at transformer layers 9 and 10. P2-D3 then showed that scalar LoRA scaling at those same layers, including scale `0.0`, does not satisfy the frozen score-repair proxy.

P2-D4 asks the next narrower causal question:

> Within the D2-selected WORLD-prefill cache locus at layers 9 and 10, is the causal mediation concentrated preferentially in key state, value state, or a joint/distributed K/V configuration?

D4 does not reopen P2 behavioral admission, D1, D2, or D3. It does not modify model parameters, ActionIntent generation, decoding policy, simulation state, or the frozen cohort.

## 2. Frozen source lineage

### D1 scientific identity

- study: `WORLD_P2_D1_DECISION_BOUNDARY_LOCALIZATION_V1`
- historical scientific details SHA-256: `0e5e62709d58168c9922645c1d05d54a7f5c417b68b3f461b4558d3706ca3b17`
- recovery summary SHA-256: `2355558f1424cacae0ba8819621c6eef532e48b59bbeeb9ab314ccdd829e1e40`
- recovery stdout SHA-256: `bbeabf9305ce2d912b33026a1b18e7f9fc629762f075b946a0e2f1031827afbe`
- sealed recovery archive SHA-256: `7c56da7213e270fe60d2d8fe67d6aabe005dc9ff5bed79bb91120244a7743e80`

### D2 scientific identity

- study: `WORLD_P2_D2_KV_CACHE_CAUSAL_LOCALIZATION_V1`
- historical scientific HEAD: `9cfa129c260173790865825f6d6283b57bac555c`
- historical result digest: `cf03450cdcde79e0f2fe78b4caf7bda6df99bec159246a15817194dcc61b9a61`
- historical/recovered exact details SHA-256: `e554f6a113597cd8d3f1d9c923f7ee4e17c59c51e9933cd398a2118f15731608`
- recovery summary SHA-256: `37dcddf79b5cc7f197d220d11bb1b0d80bfc87d65dd77c618ec5acc3a89117fb`
- recovery stdout SHA-256: `1a4d8844341751240466089424d46a5e38e54c466186bafc164b3be294cc708c`
- sealed recovery archive SHA-256: `ae48541bc474771b676717b5b2a156d6e0b9553867b25111b41f6a64e3fbfc3b`
- localization: `UNION_BIDIRECTIONAL_NONUNIVERSAL`
- selected layers: `[9, 10]`

### D3 scientific identity

- study: `WORLD_P2_D3_TARGETED_ADAPTER_SCALING_V1`
- preregistration commit: `8cbba8828fbb3f5b6bb496f2476c78b420036296`
- scientific HEAD: `ee0b1da2bbda35c026f9ca38aa7dcea92f815ce0`
- complete result digest: `f47c082fc03d0129b82ccf404f30e39b8fed76e77650a303074d4258b90fa130`
- complete details SHA-256: `8646a7d897278f639d80295766649b4ab4506e809d6b3122994339fa7b3a5f1b`
- complete summary SHA-256: `74c92110510b6d477cd97de67f3fb99879331c2529ce22949aaeb44d740152fa`
- complete stdout SHA-256: `c2f0aba8b0bd0ac2cc884db99119ee7950791175eb6ea0053243ea761dd16b88`
- sealed result archive SHA-256: `9c2090ff25dce3ae6431fe78abecb774b8ac365880c50d521b270b3766e73f54`
- selected scale: `0.0`
- repair proxy: `SCORE_PROXY_NOT_REPAIRED`

The D4 runner must verify the frozen recovery evidence identities used as inputs before any scientific measurement and again after the final measurement.

## 3. Frozen model and cache identity

D4 uses the same immutable OLMo-2-0425-1B-Instruct BF16 deployment and FA adapter lineage used by D1-D3.

The cache representation must expose exactly 16 ordered transformer layers, each with exactly one key tensor and one value tensor. BASE and FA caches must match at every layer in tensor shape, dtype, device, and sequence topology.

D4 introduces only one new intervention primitive: **component-specific cache transplantation**.

For a selected layer set `L` and component `C`:

- `C = K`: replace donor key tensors at `L` while retaining target value tensors at `L`;
- `C = V`: replace donor value tensors at `L` while retaining target key tensors at `L`.

Every rebuilt cache tensor must be cloned. Donor and source-target caches must remain unchanged.

## 4. Frozen cohort

The cohort is inherited unchanged from D1 and D2.

Full cohort:

- context classes: `QUIET`, `MESSAGE_RECEIVED`, `PROPOSAL_RECEIVED`, `OWN_PROPOSAL_PENDING`, `RECENT_INTERACTION`
- case indices: `4000..4031` inclusive
- 32 cases per class
- 160 contexts total

Screening cohort:

- same five context classes
- case indices: `4000..4003` inclusive
- 4 cases per class
- 20 contexts total

No case substitution is permitted after preregistration.

## 5. Frozen baselines and directions

For each context compute the same two source WORLD-prefill caches as D2:

- `B`: BASE WORLD-prefill cache;
- `F`: FA WORLD-prefill cache.

The selector remains BASE in every condition.

For a component candidate `X`:

- rescue: `F[B@X]` — start from F and transplant the selected BASE component(s);
- induction: `B[F@X]` — start from B and transplant the selected FA component(s).

All nonselected layers and all nonselected components remain exactly from the target cache.

## 6. Frozen component candidates

Stage A evaluates exactly these six candidates:

1. `L9_K` — key only at layer 9
2. `L9_V` — value only at layer 9
3. `L10_K` — key only at layer 10
4. `L10_V` — value only at layer 10
5. `L9_L10_K` — key only at layers 9 and 10
6. `L9_L10_V` — value only at layers 9 and 10

No attention-head, token-position, residual-stream, MLP, or parameter intervention may be added to D4 V1 after observing results.

## 7. Decision readout

D4 inherits D2's preregistered SEND/WAIT mediator axis.

For every evaluated condition:

`G = total_log_probability(WAIT) - total_log_probability(SEND)`

Thus:

- `G < 0`: SEND side of the D1 boundary;
- `G > 0`: WAIT side of the D1 boundary.

For each context:

- `G_B`: BASE baseline gap;
- `G_F`: FA baseline gap;
- `D = G_F - G_B`;
- rescue gap: `G_R(X)`;
- induction gap: `G_I(X)`;
- normalized rescue fraction: `NR(X) = (G_F - G_R(X)) / D`;
- normalized induction fraction: `NI(X) = (G_I(X) - G_B) / D`;
- symmetric mediator score: `S(X) = (NR(X) + NI(X)) / 2`.

D4 requires `D > 0` for every evaluated context. Fractions are not clipped.

Stage A may persist only WAIT and SEND continuations after the same D1 five-schema legal-set divergence point. Stage B uses full five-action D1-compatible scoring.

## 8. Stage 0 — component-patch implementation controls

Scientific screening is admitted only if all of the following hold:

1. Unpatched B/F readouts reproduce the frozen D1 source records for the same screening contexts.
2. K-only self-donor patches are exact no-ops.
3. V-only self-donor patches are exact no-ops.
4. For each tested layer scope, composing donor K and donor V component patches produces the same cache/readout as D2's full-KV transplant for that scope.
5. A K-only patch leaves the target V tensor unchanged at every selected layer.
6. A V-only patch leaves the target K tensor unchanged at every selected layer.
7. Donor and source-target cache signatures and tensor values are unchanged after every patch operation.
8. Cache type, layer count, tensor shapes, dtype, device, and sequence length remain valid after component transplantation.

Any failure is implementation/runtime evidence only and terminates the attempt before scientific interpretation.

## 9. Stage A — 20-context component screening

Evaluate rescue and induction for all six frozen candidates on all 20 screening contexts.

For every candidate report:

- median symmetric mediator score `S(X)`;
- median `NR(X)` and `NI(X)`;
- rescue sign-flip count;
- induction sign-flip count;
- WAIT/SEND score distributions overall and by context class.

Advancement rule:

- rank candidates by descending median symmetric mediator score;
- if exact ties occur, use this fixed simpler-first order:
  `L9_K`, `L9_V`, `L10_K`, `L10_V`, `L9_L10_K`, `L9_L10_V`;
- advance exactly the top one candidate to Stage B.

No magnitude threshold or post-hoc candidate substitution may be introduced.

## 10. Stage B — full-cohort confirmation

On all 160 frozen contexts evaluate and store full five-action D1-compatible scores for:

- unpatched B baseline;
- unpatched F baseline;
- rescue using the selected Stage-A component candidate;
- induction using the selected Stage-A component candidate.

Then repeat the selected rescue and induction conditions in full over all 160 contexts.

Primary confirmation report:

- selected candidate identity;
- full distribution of `G`, `NR`, `NI`, and `S` overall and by context class;
- rescue and induction sign-flip counts out of 160;
- full five-action total-rank-1 distributions;
- whether any third action overtakes WAIT and SEND;
- exact repeat serialization equality;
- descriptive comparison against the matching D2 full-KV intervention for the same layer scope when directly available from frozen D2 details.

The component/full-KV comparison is descriptive. D4 does not introduce a new behavioral-admission threshold.

## 11. Exact-repeat integrity

The selected Stage-B rescue and induction conditions must be repeated over the full 160-context cohort.

The stored repeated scientific records must be serialization-identical to the primary Stage-B selected-condition records. Any mismatch makes the D4 measurement non-admissible.

## 12. Interpretation boundary

Possible D4 outcomes must be interpreted narrowly.

A K-selected result supports stronger mediation through key state among the frozen candidate set. A V-selected result supports stronger mediation through value state among the frozen candidate set. A two-layer candidate may indicate distributed cross-layer mediation. A weak top candidate remains a valid negative mechanistic result because Stage A always advances exactly one preregistered candidate.

D4 cannot by itself establish:

- a unique attention head;
- a unique token position;
- a unique residual-stream direction;
- a unique learned semantic concept;
- generalization outside the frozen WORLD cohort;
- P2 behavioral admission.

If D4 identifies a concentrated component candidate, any head-, token-, or subspace-level decomposition requires a separately preregistered follow-up.

## 13. Integrity and preservation requirements

The run is scientifically interpretable only if all hold:

- repository HEAD descends from the D4 preregistration commit;
- D4 protocol and config are byte-identical to preregistration;
- D1, D2, and D3 frozen source identities match before and after measurement;
- canonical runtime pip-freeze identity matches the frozen runtime;
- Stage-0 component-patch controls pass;
- screening and advancement follow the frozen candidate set and tie rule;
- Stage-B exact repeats are serialization-identical;
- no retry, repair, fallback, ActionIntent generation, simulation-state commit, or weight update occurs.

After a complete integrity-passing run, advancement to another study is blocked until evidence is sealed into an archive, SHA-256 verified, copied off-machine, and independently hash-verified at the destination.
