# Amendment 001 — F0 Dataset v2 Sensor Boundary

Status: PRE-EXECUTION AMENDMENT  
Applies to: `A-LifeLM Foundation Tuning Study v1`  
Timing: before any F0_DATASET_V2 freeze, candidate screening, or Study-v1 training run.

## Decision

`VISIBLE_PEER_COUNT` is not a neural gradient target in `F0_DATASET_V2`.

The deterministic sensor layer owns:

```text
visible_peer_count = len(visible_peer_handles)
```

A separate frozen sensor-invariant suite continues to test this fact, but its
examples do not enter neural TRAIN/DEV gradient data.

All other Study-v1 grounding families remain neural targets unless a later
pre-execution amendment explicitly changes ownership.

## Rationale

The Study-v1 preregistration already defines the system boundary as:

```text
Deterministic Sensor Normalization
        +
Minimal Neural Foundation Adapter
```

and states that `VISIBLE_PEER_COUNT` is removed from neural-competence scoring
once sensor normalization is active. Leaving count examples in the neural
training objective would preserve an unnecessary optimization pressure for a
quantity the runtime computes exactly and would make the neural/sensor boundary
internally inconsistent.

This amendment therefore applies the preregistered ownership rule to the V2
dataset rather than introducing a new performance-driven hypothesis.

## Invariants

- `F0_DATASET_V1` remains byte-for-byte frozen and unchanged.
- `F0_DATASET_V2` neural splits contain no `VISIBLE_PEER_COUNT` examples.
- Sensor count probes are stored separately and have `gradient_target=false`.
- Sensor normalization does not infer message direction, proposal direction,
  trust, friendship, preference, policy, or any social meaning.
- EXP-000 canonical runtime and agent-visible ContextPack are not changed by
  this dataset/evaluation utility.
- Any future change to canonical agent-visible information still requires the
  owning architecture change process.

## Comparability

All Study-v1 trainable candidates use the same V2 neural dataset. Therefore the
first decisive comparison remains controlled:

```text
attention-only r16 NF4 QLoRA
vs
attention-only r16 BF16 LoRA
```

with quantization/precision as the intended treatment difference.

Sensor-invariant correctness is reported separately from Neural Grounding
Accuracy (NGA).
