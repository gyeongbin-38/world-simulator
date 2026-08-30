# A-LifeLM Foundation Tuning Study v1

Status: PRE-REGISTERED DRAFT  
Project: WORLD / A-LifeLM  
Purpose: identify the smallest adaptation that improves WORLD grounding and action-interface competence without injecting social policy priors or degrading pretrained capability.

## 0. Core principle

The Foundation layer is not allowed to teach agents how they should socially behave. It may only improve:

- self / peer identity grounding
- message and proposal relational grounding
- observable-state interpretation
- opaque identifier handling / copying
- action-intent serialization
- interface compliance

The Foundation layer must not encode friendship, trust, cooperation preference, social rank, mate preference, leadership, moral preference, alliance preference, aggression preference, or other social-policy priors.

The canonical system boundary for this study is:

```text
Deterministic Sensor Normalization
        +
Minimal Neural Foundation Adapter
        +
Unmodified WORLD policy / experience loop
```

## 1. Existing evidence to freeze

The following results are treated as prior evidence and must not be retroactively changed:

- FA-v1: attention-focused LoRA, hidden score ≈ 98.33%
- FA-v2: broader / all-transformer-linear adaptation, hidden score ≈ 96.62%
- Interpretation: increasing adapter coverage did not improve hidden generalization and may have damaged useful pretrained relational representations.
- Existing runs are n=1 and therefore are not sufficient to establish statistically stable architecture rankings.

All future comparisons must record seed, dataset version, tokenizer settings, target modules, precision, optimizer, scheduler, LR, rank, alpha, dropout, effective batch size, sequence length, number of optimizer steps, and evaluator version.

## 2. Research questions

RQ1. Is the remaining hidden error caused materially by QLoRA/NF4 training rather than adapter architecture?

RQ2. Can data-aware or optimizer-aware LoRA variants improve hidden relational grounding while keeping adaptation narrow?

RQ3. Does deterministic sensor normalization remove errors that should never have been delegated to the language model?

RQ4. Can the Foundation reach ≥99% neural-grounding accuracy without measurable degradation in retention or neutrality?

RQ5. Are improvements robust across seeds rather than a single favorable initialization?

## 3. Hypotheses

H1 — BF16 hypothesis  
BF16 LoRA using the same attention-only architecture as FA-v1 will match or exceed NF4 QLoRA if quantization mismatch contributes materially to residual error.

H2 — LoRA+ hypothesis  
Different learning rates for LoRA A/B matrices will improve convergence and/or final hidden score without increasing adapter coverage.

H3 — EVA hypothesis  
EVA will allocate rank toward activation subspaces actually used by the WORLD grounding data and outperform uniform-rank vanilla LoRA at equal or similar parameter budget.

H4 — Sensor-boundary hypothesis  
Deterministic sensor normalization will eliminate counting / directly-computable observable errors while reducing pressure on the neural adapter.

H5 — Minimal-intervention hypothesis  
Attention-focused selective adaptation will preserve retention and neutrality better than broad all-linear adaptation.

## 4. Ownership boundary: deterministic vs neural

### 4.1 Deterministic sensor-owned fields

These are computed by runtime and supplied canonically:

- `self_handle`
- normalized list of `visible_peer_handles`
- `visible_peer_count = len(visible_peer_handles)`
- message object identifiers
- message `sender_handle`
- message `receiver_handle`
- proposal object identifiers
- proposal `owner_handle`
- proposal `target_handle`
- object existence / absence facts that are directly present in the observation
- canonical ordering / schema validation

The deterministic layer must not compute social interpretations such as trust, friendship, rank, desirability, cooperation value, threat, alliance membership, or preferred action.

### 4.2 Neural Foundation-owned tasks

The neural adapter remains responsible for:

- SELF_IDENTITY
- PEER_IDENTITY
- PEER_HANDLE_LOOKUP
- OPAQUE_HANDLE_COPY
- MESSAGE_SENDER
- MESSAGE_RECEIVER
- MESSAGE_DIRECTION
- PROPOSAL_ID
- PROPOSAL_OWNER
- PROPOSAL_TARGET
- PROPOSAL_DIRECTION
- INCOMING_PROPOSAL_IDENTIFICATION
- OUTGOING_PROPOSAL_IDENTIFICATION
- VISIBLE_VS_NOT_VISIBLE_FACT when the task requires semantic grounding rather than raw schema validation
- ALREADY_SELECTED_ACTION_SERIALIZATION

`VISIBLE_PEER_COUNT` is removed from neural-competence scoring once sensor normalization is active. It remains separately tested as a deterministic sensor invariant.

## 5. Evaluator v2

### 5.1 Closed-set constrained scoring

For semantic tasks with known candidate sets, evaluation must compare candidate likelihoods rather than rely on unconstrained free-form generation.

Examples:

```text
MESSAGE_DIRECTION ∈ {INCOMING, OUTGOING}
PROPOSAL_DIRECTION ∈ {INCOMING, OUTGOING}
VISIBLE_VS_NOT_VISIBLE_FACT ∈ {VISIBLE, NOT_VISIBLE}
```

For identifiers, exact normalized-token matching is used.

For serialization, schema-validity and semantic correctness are scored separately.

### 5.2 Metrics

Primary:
- Neural Grounding Accuracy (NGA): macro-average over neural-owned semantic families.
- Family Accuracy: per semantic family.
- Worst-Family Accuracy.
- Seed Mean / StdDev.

Secondary:
- Serialization Validity Rate.
- Deterministic Sensor Correctness.
- Base Retention Delta.
- Neutrality Shift.
- Training stability: NaN/overflow, loss spikes, gradient norm anomalies.
- Compute: peak VRAM, wall-clock, optimizer steps.

### 5.3 Retention metric

A fixed retention suite must be frozen before candidate training. It should include:
- general language completion
- basic factual / commonsense prompts
- simple reasoning
- instruction compliance unrelated to WORLD

The exact suite and prompts must be immutable after the first formal run.

### 5.4 Neutrality audit

A frozen set of WORLD situations will intentionally leave multiple socially meaningful actions equally permissible.

Measure:
- action distribution shift relative to the unadapted base
- KL or Jensen-Shannon divergence where distributions are available
- deterministic propensity deltas for ACCEPT / REJECT / SEND / WAIT / PROPOSE
- scenario-specific bias deltas

No candidate may be promoted solely on grounding accuracy if it introduces systematic policy preference.

## 6. Dataset v2

### 6.1 Dataset construction

Target full train size: 4096 examples.

Every relational family must contain:
- easy
- medium
- hard
- minimal-pair
- counterfactual
- adversarial / distractor examples

### 6.2 Minimal-pair requirement

Pairs should preserve surface structure while changing only the relation needed for the label.

Examples:

```text
self=A, sender=A, receiver=P7  -> OUTGOING
self=A, sender=P7, receiver=A  -> INCOMING
```

```text
self=A, proposal_owner=A, target=P7 -> OUTGOING
self=A, proposal_owner=P7, target=A -> INCOMING
```

### 6.3 Split rule

No exact template instance, identifier tuple, or generated minimal-pair sibling may cross train/dev/hidden boundaries.

Hidden remains sealed.

### 6.4 Screening subset

A deterministic 1024-example train subset and 256-example dev subset are sampled once from Dataset v2 and then frozen for all screening candidates.

## 7. Model / tokenizer conventions

Base model must remain fixed for the entire Study v1.

For OLMo-2 experiments:
- use the canonical model/tokenizer pairing selected for the project
- explicitly audit BOS behavior
- enable the OLMo-required BOS convention
- disable slow tokenizer unless a reproducibility test demonstrates a reason not to
- record chat template / prompt template hash
- record tokenizer revision

No candidate may silently change prompt formatting or tokenizer behavior.

## 8. Experiment matrix

### Stage 0 — evaluator and sensor validation

S0-A:
- unadapted base
- evaluator v2
- no sensor normalization

S0-B:
- FA-v1 checkpoint
- evaluator v2
- no sensor normalization

S0-C:
- FA-v1 checkpoint
- evaluator v2
- sensor normalization enabled

Purpose:
- quantify how much of the previous gap was evaluator / sensor abstraction rather than learning.

### Stage 1 — cheap screening

Use:
- 1024 train examples
- 256 dev examples
- 3 seeds
- target 150–200 optimizer steps
- identical data ordering policy per seed across paired candidates

Candidates:

A — Vanilla QLoRA baseline
- attention-only target modules
- NF4
- r=16
- canonical FA-v1-equivalent settings

B — BF16 LoRA
- same target modules / r / alpha / data as A
- BF16 base training
- no 4-bit quantization

C — BF16 LoRA+
- same architecture as B
- LoRA+ optimizer
- initial `loraplus_lr_ratio=16`
- preserve total step budget

D — BF16 EVA-LoRA
- attention-only target modules
- base r=16
- EVA initialization
- `rho=2.0` initial setting
- activation statistics computed only from the training split

E — BF16 EVA-LoRA + Sensor Normalization
- same neural configuration as D
- deterministic sensor normalization active
- neural score excludes deterministic-only fields

Optional F — PiSSA
- only if A–E fail promotion requirements or quantization mismatch remains unresolved

Optional G — LoRA-GA
- only after implementation/reproducibility audit

DoRA is excluded from Stage 1 because it increases adaptation freedom and is lower priority under the minimal-intervention objective.

Broad all-linear LoRA is excluded from Study v1 screening unless later required as a negative control.

## 9. Target modules

Initial attention-focused target set for Hugging Face OLMo-2:

```text
q_proj
k_proj
v_proj
o_proj
```

Before training, the runner must enumerate matched trainable modules and abort if the resolved module set differs from the expected set.

No MLP target is enabled in the default screening candidates.

A later selective-MLP ablation may be introduced only after EVA rank diagnostics identify a clear justification.

## 10. Stage 1 selection gate

Each candidate gets 3 seeds.

Hard rejection:
- training instability
- serialization validity regression >1 percentage point
- retention degradation >1.0 percentage point on the frozen retention suite
- detectable systematic neutrality failure
- mean NGA worse than paired baseline by >0.25 percentage points

Advance rule:
- top two candidates by mean NGA,
- provided they pass all hard rejection gates.

Tie-break order:
1. lower seed variance
2. higher worst-family accuracy
3. smaller neutrality shift
4. better retention
5. lower compute / VRAM

## 11. Stage 2 — formal run

Only top two Stage-1 candidates advance.

Protocol:
- full 4096-example Dataset v2
- full planned epoch budget
- 5 seeds
- sealed hidden evaluation
- evaluator v2
- retention suite
- neutrality audit
- deterministic sensor invariant suite
- fixed inference settings

### Formal promotion criteria

A candidate can become the Foundation candidate only if:

1. mean hidden NGA ≥ 99.0%
2. worst seed hidden NGA ≥ 98.5%
3. no major semantic family < 97.0%
4. serialization validity ≥ 99.9%
5. deterministic sensor correctness = 100%
6. retention degradation ≤ 1.0 percentage point
7. no pre-registered neutrality failure
8. result is not dependent on one outlier seed

If no candidate passes all gates, no Foundation is promoted. Study v2 is designed from the failure analysis.

## 12. Statistical reporting

Report for every candidate:
- each seed separately
- mean
- standard deviation
- 95% bootstrap confidence interval where useful
- paired differences against the baseline with identical seeds
- family-level confusion / error table

Do not report only the best seed.

## 13. Required artifacts per run

Every run directory must contain:

```text
config.yaml
environment.txt
git_commit.txt
dataset_manifest.json
dataset_hashes.json
tokenizer_manifest.json
prompt_template.txt
train_log.jsonl
metrics_dev.json
metrics_hidden.json        # formal stage only
retention.json
neutrality.json
sensor_invariants.json
adapter/
failure_examples.jsonl
```

The hidden set itself must never be copied into ordinary run outputs.

## 14. Stop conditions

Stop a candidate early if:
- loss becomes NaN / Inf
- evaluator corruption is detected
- target-module resolution differs from pre-registered configuration
- tokenizer/prompt hash mismatch occurs
- sensor-normalization schema mismatch occurs

Do not stop merely because an intermediate dev result looks worse unless the failure is structural.

## 15. Immediate next implementation order

1. Freeze current FA-v0/v1/v2 evidence.
2. Implement Evaluator v2 with constrained candidate scoring.
3. Implement deterministic Sensor Normalizer v1.
4. Build Dataset v2 generator + leakage checks.
5. Add run manifest / hashing.
6. Re-evaluate FA-v1 under Evaluator v2.
7. Run paired Stage-1 A vs B first: NF4 QLoRA vs BF16 LoRA.
8. If infrastructure is valid, run C/D/E across the same 3 seeds.
9. Select top two using the pre-registered gate.
10. Run Stage 2 with 5 seeds.

## 16. First decisive experiment

The first training experiment after infrastructure validation is:

```text
FA-v1-equivalent attention-only r16
NF4 QLoRA
vs
FA-v1-equivalent attention-only r16
BF16 LoRA
```

All variables except quantization / precision are held constant.

This experiment has the highest information value because it separates a possible quantization-training mismatch from architecture / dataset limitations before introducing EVA or optimizer changes.

## 17. Interpretation rules

- Higher train fit without higher hidden NGA is not progress.
- More trainable parameters are not automatically better.
- Deterministic observables should not be used as evidence of neural intelligence.
- A gain that damages retention or neutrality is rejected.
- A result seen in one seed is a lead, not a conclusion.
- If sensor normalization solves an error class, that error is reclassified as an interface-design issue rather than a neural-capability improvement.
