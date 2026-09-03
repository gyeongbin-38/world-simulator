# WORLD P2-D1 Pre-Inference Implementation Note V1

Status: IMPLEMENTATION FROZEN FOR RUNTIME VALIDATION; NO P2-D1 MODEL FORWARD HAS BEEN PERFORMED UNDER THIS IMPLEMENTATION.

This note records implementation semantics fixed before observing any P2-D1 model scores. It does not modify the preregistered scientific question, reopen P2, introduce a behavioral threshold, or establish Founder Freeze.

## Source scientific freeze

- P2-D1 preregistration/config freeze commit: `44d8df09b452143ac8007a82d8d9ffd6f2593322`.
- Frozen P2 source result: `C10_NOT_BEHAVIORALLY_ADMITTED`.
- Frozen P2 source result digest: `4226c5909fd13d8d769436d344a221d6f0c1746b08466ff6f5eb03303c0be563`.
- Frozen P2 canonical archive SHA-256: `61a19717cf089fb59b43e2b52efc31e28036449418e3aeba69c8dd0bbad17790`.
- Founder Freeze remains `NOT_ESTABLISHED`.

## Decision-boundary implementation semantics

For each P2 R3 context under C00 or C10, the implementation reproduces the P2 split cached topology: WORLD context is forwarded exactly once in Phase A, the frozen I3 suffix is forwarded in Phase B, and WORLD context is never recomputed after the adapter-state boundary.

Five independent LM Format Enforcer constraints are built from the canonical forced-action I3 schemas in frozen internal order `WAIT`, `SEND`, `PROPOSE`, `ACCEPT`, `REJECT`.

Starting immediately after the I3 suffix, the implementation advances a common constrained-greedy prefix only while all five forced schemas expose exactly identical canonicalized legal token-ID sets. The greedy tie-break is the previously hardened lowest-token-ID tie break. The first state at which the five legal sets are not identical is the preregistered action-branch divergence point. Shared tokens before this point are excluded from branch scores.

From the identical cloned cache and logits at divergence, each target branch is followed counterfactually under its own forced schema. At each branch step the highest-logit legal token is chosen deterministically, while raw token log-probability is measured under the full-vocabulary model distribution. Tokens are accumulated only from divergence until the target forced schema is the sole surviving branch compatible with the observed continuation. This logical uniqueness is the implementation meaning of `ACTION_LABEL_UNIQUELY_DETERMINED` under the five frozen forced-action schemas.

The diagnostic therefore scores one deterministic constrained-greedy tokenization path per branch. It does **not** marginalize probability mass over alternate tokenizer paths that might encode the same JSON/action label. Both total and token-count-normalized mean log-probability are retained, and the exact branch token IDs and explicit token counts are persisted so any tokenization effect remains observable.

The 64-token common-prefix and 32-token branch-continuation limits are fail-closed implementation guards only. Hitting either guard is an implementation/infrastructure failure, not scientific evidence and not a negative localization result.

## Integrity hardening

- C00 and C10 only; no C01/C11 execution.
- Full 160-context primary cohort per condition and a full exact repeat per condition: 640 scored probes total.
- Compiled WORLD context bytes and rendered I3 request bytes must match frozen P2 R3 source records.
- During model execution, context/prefix/combined token IDs must match frozen P2 R3 source records exactly.
- P2 R3 summary/details/stdout/archive are read-only, hashed before and after D1, and the canonical P2 archive SHA is checked against its frozen value.
- Required P2 source files are additionally compared with the corresponding canonical archive members. The hardened entrypoint caches those member bytes after one archive scan to avoid repeated multi-gigabyte decompression; the compressed archive itself is still re-hashed after D1 so mid-run source mutation remains detectable.
- No ActionIntent generation, simulation-state commit, weight update, retry, repair, fallback, scalar correction, sampling, or semantic action hint exists in the D1 path.
- Primary/repeat serialized records must match exactly for integrity admission; numerical repeat deltas are also reported explicitly.

## Descriptive localization

No new empirical threshold is introduced. `RANK_STABLE_SCORE_SENSITIVE_NDA_DOMINANCE` is used only when total-rank behavior remains NDA-stable and context-score movement exceeds the observed exact-repeat numerical noise. `ACTION_SCORE_CONTEXT_INSENSITIVE` is used only when the matched context effect is no larger than exact-repeat numerical noise. Any action-rank change uses the preregistered `RANK_CONTEXT_SENSITIVE` tag. Otherwise the result is `MIXED_OR_UNRESOLVED`.

These are diagnostic labels only. P2 remains unchanged regardless of D1 outcome.

## Runtime-validation boundary

Before the first P2-D1 model forward on a restored/new Pod, the implementation must pass the dedicated P2-D1 unit/contract tests and hardened `validate` preflight on the canonical frozen runtime. Any failure before or during that validation is implementation evidence only and must be fixed without changing the frozen P2-D1 scientific contract.
