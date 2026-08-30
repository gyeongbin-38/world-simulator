# Foundation Tuning Study v1 — Post-Stage-0 Boundary Amendment 01

Status: POST-STAGE-0 ARCHITECTURAL BOUNDARY CORRECTION

This append-only amendment records a boundary correction made after execution
of `F0_FOUNDATION_STAGE0_EVAL_V2_V1`. It does not rewrite the Study v1
preregistration, its historical promotion criteria, or any historical result.
The amendment is motivated by task ownership: a deterministic sensor owns
visible-count derivation, while an already-selected action codec tests
transport compliance rather than grounding or policy selection.

## Operational measurement layers

### Neural grounding competence

Neural Grounding Accuracy (NGA) measures the 14 remaining relational and
perceptual grounding families. These require the model to map visible,
opaque, directed facts to the requested answer. The model is not asked to
choose a social action by this metric.

`VISIBLE_PEER_COUNT` is excluded because its value is computed by the
deterministic Sensor Normalizer. `ALREADY_SELECTED_ACTION_SERIALIZATION` is
excluded because its supplied action and payload are already selected; the
task is codec/transport compliance.

For the recovered FA-v1 Stage 0 result, the derived operational grounding
result is:

```text
3128 / 3136 = 0.9974489795918368
```

The worst grounding family is `PROPOSAL_OWNER`:

```text
0.9866071428571429
```

### Motor, transport, and codec compliance

`ALREADY_SELECTED_ACTION_SERIALIZATION` remains a separately reported motor
and interface diagnostic. Stage 0 recorded schema validity and semantic
correctness of `220 / 224 = 0.9821428571428571`. This diagnostic does not
become a policy metric and does not make the model an action selector.

The live WORLD contract remains unchanged:

```text
model output
  -> ModelActionCandidate
  -> CognitionGateway
  -> ActionIntent
```

The gateway continues to bind actor, tick, and intent identity. No
deterministic action chooser replaces the model decision path.

### Deterministic sensor invariants

`VISIBLE_PEER_COUNT` is a sensor-owned invariant:

```text
visible_peer_count = len(visible_peer_handles)
```

Stage 0 S0-C recorded `224 / 224 = 1.0`. Sensor correctness is reported
separately and is not included in the 14-family neural NGA.

## Historical criteria and scope

The original Study v1 promotion criteria remain the historical preregistered
criteria. This amendment does not change their failure/pass semantics,
thresholds, or chronology. The 14-family value is an operational acceptance
boundary for the recovered artifact and is not a retroactive rewrite of the
original admission decision.

This amendment does not establish a training-recipe promotion. Multi-seed
reproducibility, retention, neutrality, and other recipe-level evidence remain
separate requirements.

