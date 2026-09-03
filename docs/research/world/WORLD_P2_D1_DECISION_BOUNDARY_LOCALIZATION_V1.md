# WORLD P2-D1 Decision-Boundary Localization V1

Status: PREREGISTERED DIAGNOSTIC. This protocol does not reopen or relabel P2. The frozen P2 R3 result remains `C10_NOT_BEHAVIORALLY_ADMITTED`, with P2-G2 failed and P2-G3 not run by protocol. Founder Freeze remains `NOT_ESTABLISHED`.

## Question
Determine whether the P2 C10 behavioral collapse (`NO_DIRECTED_ACTION` for all 160 contexts) is caused primarily by a rank-stable global selector bias that masks context-sensitive score movement, or by loss of context-sensitive action information at the P2 decision boundary.

## Source evidence
Use the immutable P2 R3 cohort and evidence only as provenance/reference. Do not alter, overwrite, or reinterpret the P2 admission gates. Source cohort: cases 4000..4031 across `QUIET`, `MESSAGE_RECEIVED`, `PROPOSAL_RECEIVED`, `OWN_PROPOSAL_PENDING`, `RECENT_INTERACTION`.

## Conditions
Primary diagnostic: C10 = FA-v1 WORLD-context prefill, adapter OFF for selector continuation.
Comparator: C00 = BASE WORLD-context prefill, BASE selector continuation.
No C01/C11 execution is required for D1.

## Topology
Use the same cached split topology as P2: WORLD context exactly once in Phase A; retain PKV; switch adapter state; no WORLD-context recomputation; no simulation-state commit; no weight update. The diagnostic is researcher-only scoring and must not generate an ActionIntent or modify the P2 primary artifacts.

## Decision-boundary probe
The probe must remain inside the frozen I3 action codec semantics. For each context and each condition, identify the earliest constrained continuation state at which the five frozen action branches cease to have identical legal continuation sets under the corresponding forced-action I3 schemas. This is the action-branch divergence point.

From the exact common cached state at that divergence point, score each frozen action branch counterfactually under its forced-action I3 schema without feeding the resulting branch choice back into WORLD. Accumulate raw token log-probability until the action label is fully determined; record both total and token-count-normalized mean log-probability. Syntax tokens shared before branch divergence are excluded from the branch score. Candidate branch ordering is the frozen internal order `WAIT`, `SEND`, `PROPOSE`, `ACCEPT`, `REJECT`; model labels are taken from the canonical `ActionPresentation` and are not rewritten.

The probe must fail closed if: the five forced schemas diverge before a common legal prefix exists; the divergence point cannot be located deterministically; a forced branch cannot reach a uniquely determined action label; context bytes/token IDs differ from P2; the runtime or source evidence hashes differ; or any WORLD context is recomputed after the phase switch.

## Measurements
For every case/context/condition record: branch total log-probabilities, mean log-probabilities, ranks using total score and mean score, rank-1 branch, `NO_DIRECTED_ACTION` total-score margin over the best non-NDA branch, token counts, divergence step, common-prefix token IDs, and exact phase/runtime provenance.

For matched cases compare each non-quiet context to QUIET under C10: per-label total-score delta, per-label mean-score delta, maximum absolute score-vector delta, NDA-margin delta, any rank change, and rank-1 change. Also compare paired C10 versus C00 at each context to quantify the FA-prefill shift with the selector held BASE.

## Descriptive localization tags
These tags are diagnostic only and are not pass/fail gates for P2.

- `RANK_STABLE_SCORE_SENSITIVE_NDA_DOMINANCE`: C10 rank-1 remains NDA across the matched set while at least one non-quiet class shows reproducible paired action-score movement relative to QUIET.
- `ACTION_SCORE_CONTEXT_INSENSITIVE`: C10 action-score vectors and NDA margins are effectively unchanged across matched contexts within exact-repeat numerical noise.
- `RANK_CONTEXT_SENSITIVE`: at least one matched C10 case changes action rank or rank-1 branch across contexts.
- `MIXED_OR_UNRESOLVED`: evidence does not cleanly support the above localizations.

No numerical sensitivity threshold may be invented after observing D1. Report raw effect distributions and exact-repeat numerical noise. If a later binary threshold is desired, preregister it in a separate experiment.

## Integrity requirements
- Exact model/checkpoint/adapter/tokenizer/runtime identities inherited from P2.
- Canonical pip-freeze SHA-256 must remain `a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf`.
- P2 R3 source summary/details/stdout/archive are read-only and hashed before/after D1.
- No retries, repair, fallback, EOS suppression, sampling, scalar correction, action-frequency target, or semantic action hint.
- Exact repeat of every scored condition must be bitwise/evidence identical where serialized values permit; floating values must be reported at full stored precision and repeat deltas separately.
- Any infrastructure or implementation failure is not scientific evidence and must be preserved as a versioned failed attempt.

## Interpretation boundary
D1 can localize why C10 failed P2-G2. It cannot promote C10, establish autonomous policy competence, establish long-horizon social behavior, or establish Founder Freeze. Any architectural change (structured grounding artifact, selector replacement, cache isolation, calibration, or retraining) requires a new preregistered experiment after D1.