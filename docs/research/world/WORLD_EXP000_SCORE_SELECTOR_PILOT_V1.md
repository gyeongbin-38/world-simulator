# WORLD EXP-000 Score-Selector Pilot V1

Status: **PREREGISTERED / NO NEW MODEL FORWARD YET**

## 1. Purpose

The existing deterministic kernel, durable persistence, replay, and LIVE EXP-000 controller are integrated. The remaining blocker is action selection: prior real-model and P2 runs show hard-argmax collapse (C00 nearly always DIRECT_TEXT; C01/C10/C11 always NO_DIRECTED_ACTION), while P2-D1 shows that non-rank-1 action-score geometry remains context-sensitive under C10.

This pilot tests a bounded two-stage selector that samples an action label from the model's own preregistered branch-score geometry before conditional payload generation. It is not an activity-targeting heuristic and does not encode a preferred social action.

## 2. Frozen source evidence

- P2 result: `C10_NOT_BEHAVIORALLY_ADMITTED`
- P2-D1 status: `P2_D1_MEASUREMENT_COMPLETE`
- P2-D1 details SHA-256: `0e5e62709d58168c9922645c1d05d54a7f5c417b68b3f461b4558d3706ca3b17`
- P2-D4 result digest: `e7a7bfae9ecaaebf862727ed31b228be921ea6a4ac889520b6361279c3ad76d6`
- P2-D4 selected mediator candidate: `L9_V`

No D5 mechanistic study is required for this pilot.

## 3. Frozen phase architecture

The selector uses the C10 phase decomposition:

- WORLD prefill: FA-v1
- action scoring / selector phase: BASE

This preserves the phase condition in which D1 established hidden context-dependent score movement beneath a WAIT-dominant hard argmax.

## 4. Frozen action score

Action order is exactly:

1. `WAIT`
2. `SEND`
3. `PROPOSE`
4. `ACCEPT`
5. `REJECT`

For each action, the selector uses the existing D1/I3 **mean branch log probability** from the common decision boundary.

The mean branch score is treated as an energy for categorical selection. It is not described as a calibrated policy probability and is not variance explained.

No scalar correction, per-action bonus, frequency target, or researcher-defined utility is permitted.

## 5. Frozen stochastic selector

Temperature is fixed at:

`T = 1.0`

No temperature sweep is permitted in the primary pilot. T=1.0 means the stored mean branch log probabilities are used without rescaling.

For scores `s_i`, define categorical weights:

`p_i = exp(s_i - max(s)) / sum_j exp(s_j - max(s))`

Selection uses one deterministic uniform variate derived from immutable opportunity identity. The seed material is the UTF-8 string:

`WORLD_EXP000_SCORE_SELECTOR_V1|<run_id>|<tick>|<opportunity_id>|<agent_id>`

Compute SHA-256 of that exact string. Interpret the 256-bit digest as unsigned integer `n`. Define:

`u = (n + 0.5) / 2^256`

Choose the first action in the frozen action order whose cumulative categorical probability is greater than or equal to `u`.

This selector is therefore reproducible, completion-order invariant, and independent of wall-clock timing or process-global RNG state.

## 6. No legality mask in V1

The primary V1 selector does **not** mask actions based on hidden mechanics or researcher preference.

If the selected action cannot produce a domain-valid payload in the current visible context, the existing strict codec/gateway/domain validation path may reject it. A rejection produces no fallback action and does not silently become WAIT.

A later separately versioned pilot may evaluate a mechanics-only availability mask, but V1 must not introduce one post hoc.

## 7. Conditional payload generation

After the selector chooses one action label, the same frozen C10 runtime generates only the payload required by that selected action under the existing I3 typed contract.

The payload stage must not re-select the action.

No retry, fallback, repair, hidden target injection, preferred proposal ID, preferred message, or social reward is allowed.

The existing `CognitionGateway` remains the sole authority for actor, tick, opportunity, and intent identity. `LawValidator` and the deterministic commit barrier remain the only authority for canonical mutation.

## 8. Offline source-based feasibility record

Before any new model forward, the already-recorded D1 C10 mean-score geometry at T=1.0 gave the following exploratory average categorical masses across 160 frozen contexts:

- WAIT: `0.5231`
- SEND: `0.3688`
- PROPOSE: `0.0555`
- ACCEPT: `0.0467`
- REJECT: `0.0060`

Descriptive context shifts versus QUIET included:

- MESSAGE_RECEIVED: WAIT lower and SEND higher
- RECENT_INTERACTION: WAIT lower and SEND higher
- PROPOSAL_RECEIVED: ACCEPT mass modestly higher

These observations motivate the pilot but are not primary pass/fail criteria and must not be described as calibrated behavior probabilities.

Higher temperatures were observed to increase PROPOSE/ACCEPT mass while flattening context differences. Therefore T>1.0 is not admitted merely to force activity.

## 9. Primary implementation gates before GPU use

The selector implementation must pass CPU tests proving:

1. exact categorical probabilities from known score vectors;
2. exact hash-derived `u` reproducibility;
3. completion-order invariance;
4. no dependence on Python/global RNG state;
5. no action-frequency bonus or post-selection action rewrite;
6. no legality mask in V1;
7. selected label is immutable before payload generation;
8. malformed/domain-invalid payload is rejection, never fallback WAIT;
9. durable replay does not invoke model cognition again;
10. existing deterministic kernel/lifecycle/persistence tests remain green.

No GPU pilot may start until these tests pass and the implementation commit is frozen.

## 10. First GPU pilot scope

After CPU admission, run a deliberately small LIVE EXP-000 pilot before any long world:

- founders: 3
- bounded horizon: 20 ticks
- C10 score selector V1
- T=1.0
- deterministic hash selector above
- real OLMo base + frozen FA-v1
- SQLite durable state + CAS evidence
- no batching unless already proven equivalent
- no retry/fallback/repair
- no neural heredity
- no resources/geography/game mechanics

Record at minimum:

- selected score vector and selected action label per opportunity;
- selector seed material digest and `u`;
- payload generation evidence;
- parser/domain/commit status;
- messages, proposals, accepts/rejects, births, deaths;
- state hash per committed tick;
- restart/replay model-call delta;
- exact model/tokenizer/adapter/runtime identities.

## 11. Interpretation bounds

A successful pilot may establish that the score-driven selector produces a mechanically coherent, replayable live trajectory using model-derived action-score geometry.

It does not establish social intelligence, optimal action calibration, natural reproductive competence, evolutionary fitness, culture, language evolution, or Founder Freeze.

Activity is descriptive. No minimum SEND/PROPOSE/ACCEPT/birth count may be invented after observing the run.
