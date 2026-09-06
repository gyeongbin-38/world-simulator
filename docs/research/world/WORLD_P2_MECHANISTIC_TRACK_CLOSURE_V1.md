# WORLD P2 Mechanistic Track Closure V1

Status: **CLOSED FOR CURRENT ENGINEERING MILESTONE**

## Scope

This record closes the current P2 mechanistic localization sequence after P2-D4. It does not assert that the model mechanism is fully interpreted, nor does it prohibit future separately preregistered mechanistic studies.

## Evidence chain

- P2 behavioral admission remained `C10_NOT_BEHAVIORALLY_ADMITTED`.
- P2-D1: FA WORLD-prefill causally shifted the fixed BASE selector from SEND-dominant to WAIT-dominant across the frozen cohort while context-sensitive action evidence remained below rank-1.
- P2-D2: strong bidirectional but nonuniversal mediation localized to WORLD-prefill KV state at layers 9 and 10.
- P2-D3: targeted scalar LoRA scaling at layers 9 and 10, including scale `0.0`, did not repair the preregistered score proxy.
- P2-D4: `L9_V` was selected as the strongest preregistered single-component mediator candidate; full-cohort median symmetric mediator score `0.7402240896358543`, rescue flips `62/160`, induction flips `96/160`, exact repeat pass.

## Closure rationale

The current platform objective is not exhaustive mechanistic interpretability. The required engineering question was whether the WORLD-prefill pathway causally influences downstream action selection and whether that influence can be localized beyond a purely behavioral correlation.

D1-D4 provide affirmative causal evidence and a bounded component-level localization. Additional head-, token-, residual-, circuit-, or feature-level decomposition would be scientifically useful but is not required to begin the live artificial-life experiment milestone.

## Next milestone

Proceed to **LIVE EXP-000 integration** with the following boundary:

1. real-model cognition participates in the deterministic tick barrier;
2. multiple agents communicate through committed messages;
3. agents may originate reproduction proposals and explicitly accept/reject them;
4. successful births create new agents that activate on the next tick;
5. deterministic lifespan rules produce irreversible natural death;
6. lineage, messages, births, deaths, proposals, raw model evidence, and canonical state are durably recorded;
7. restart/replay does not create additional cognition opportunities or silently re-call the model;
8. researcher observation is read-only and cannot become simulation authority.

Neural heredity, resource ecology, physical geography, and game mechanics remain outside this milestone unless separately admitted.