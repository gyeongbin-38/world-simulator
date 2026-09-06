# WORLD EXP-000 Live Grounding Pilot V1

Status: **PREREGISTERED / NO PILOT MODEL FORWARD YET**

## 1. Purpose

This is the first bounded continuous LIVE EXP-000 run that integrates the admitted proposal-handle grounding layer into the previously admitted score-selected multi-agent runtime.

The narrow engineering/scientific question is:

> Can the existing real-model multi-agent WORLD trajectory run continuously with context-local proposal handles for already-selected ACCEPT/REJECT payloads, while preserving the frozen action selector, canonical world authority, durable replay, and no-retry/no-fallback semantics?

This pilot is not an admission test for social intelligence, reproductive competence, evolution, culture, civilization, or stable population dynamics. Births, LawValidator admissions, and action frequencies are descriptive outcomes only.

## 2. Frozen source evidence

This pilot is authorized by the following bounded evidence chain:

- first LIVE EXP-000 result digest: `b82267d7769cbc4dc56aaa3c5f82e5e66b1b669ef407b4c58d1a994b4ae29f00`
- first LIVE EXP-000 canonical archive SHA-256: `b9d6e31df6e01e1ddabd943b40601255c7d80361b3eb5b3c217f25f5cc5b36e3`
- first LIVE EXP-000 off-machine hash verification: PASS
- grounding pilot preregistration commit: `8f77bbefd70bcdb54c7fb8d36542166375057281`
- proposal-handle implementation admission HEAD: `921fa52e0107c90fb80a2a8bea4251695cc62fd6`
- grounding source-smoke execution commit: `58bb49262efa61cef6c32b2db90258e12c765e77`
- grounding smoke result digest: `bbbca1f5c278ea21fcc4ec203e3ceacbe4a1087806f89dfb629105214d74f5d5`
- grounding smoke manifest SHA-256: `aedfa2f58c9b127ff9c04e5d79bebe7c7b9e892c831fa5ffac385abcff505260`
- grounding smoke canonical archive SHA-256: `ca3ae00fb89dfbb628254410189328381ae0901b8bb7d502f93fe6026e918dd3`
- grounding smoke seal `SHA256SUMS` SHA-256: `31ff48bfe03e256e95f70c6c82a1028b51f3f5f5c0e19af11854555d44b35675`
- grounding smoke off-machine destination hash verification: PASS

The grounding smoke reconstructed three exact source contexts, reran only the already-selected ACCEPT/REJECT payload stage, resolved local handles to canonical proposal IDs, preserved snapshot identity, performed zero simulation commits, and obtained descriptive LawValidator admission in 2 of 3 cases.

## 3. Frozen model/runtime identity

Unchanged from the admitted parent LIVE pilot:

- base: `allenai/OLMo-2-0425-1B-Instruct`
- base revision: `48d788eca847d4d7548f375ad03d3c9312f6139e`
- base checkpoint SHA-256: `36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f`
- FA-v1 adapter SHA-256: `46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec`
- adapter config SHA-256: `687100a0b6340b6096ca1e86066d3c13224b3c8e14ce9fb1b0cf78a52a8bdb7d`
- tokenizer aggregate SHA-256: `c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff`
- model/config aggregate SHA-256: `eeed26d20a24ad35479aa33b690b196096c5f98fee8bc43d816c3bd314987c38`
- canonical runtime pip-freeze SHA-256: `a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf`
- runtime package count: `60`
- hardware class: NVIDIA A40, BF16

No training, weight update, adapter merge, quantization change, tokenizer change, or model substitution is allowed.

## 4. Frozen cognition architecture

The score/action-selection stage remains exactly the parent score-selector V1:

1. compile ContextPack from one committed snapshot;
2. WORLD prefill under FA-v1;
3. switch to BASE for the frozen D1/I3 five-action score measurement;
4. action order: `WAIT`, `SEND`, `PROPOSE`, `ACCEPT`, `REJECT`;
5. use mean branch log probability;
6. apply `T=1.0` softmax with no per-action correction;
7. derive the deterministic categorical variate from the existing opportunity-identity SHA-256 rule;
8. freeze the selected action before payload generation.

Payload behavior:

- `WAIT`: unchanged, no payload stage;
- `SEND`: unchanged baseline forced-I3 payload path;
- `PROPOSE`: unchanged baseline forced-I3 payload path;
- `ACCEPT` / `REJECT`: if proposal references are visible, render proposal IDs as deterministic local handles `R0`, `R1`, ... and constrain `proposal_id` to the visible handle domain; resolve the generated handle back to its exact canonical proposal ID before `CognitionGateway` binding;
- `ACCEPT` / `REJECT` with no visible proposal reference: use the unchanged baseline payload path.

The handle layer is post-selection and cannot change the selected action.

## 5. Explicit non-interventions

This pilot does **not** add:

- action-availability masking;
- law-eligibility filtering of handle candidates;
- retry, fallback, repair, or resampling;
- action rewriting to WAIT;
- agent-ID aliasing or target-agent grounding;
- self-target prevention in the model interface;
- action bonuses or target-frequency objectives;
- social reward;
- heredity, resources, geography, or game mechanics.

For ACCEPT/REJECT, the allowed handle set is all proposal references visible under the existing ContextPack, not only law-admissible incoming pending proposals. `LawValidator` remains the sole admission authority.

## 6. Frozen run configuration

- study ID: `WORLD_EXP000_LIVE_GROUNDING_PILOT_V1`
- run ID: `WORLD_EXP000_LIVE_GROUNDING_PILOT_V1_R1`
- founders: `EXP000_FOUNDER_A`, `EXP000_FOUNDER_B`, `EXP000_FOUNDER_C`
- founder count: `3`
- horizon: `20` ticks
- fixed lifespan: `20` ticks
- maturity delay: `0` ticks
- refractory interval: `0` ticks
- population capacity: `6`
- context policy: existing `exp000-context` v1.0.0
- same-tick peer outputs: not visible
- batching: disabled
- payload sampling: disabled; greedy constrained completion
- score-selector temperature: `1.0`
- neural heredity: disabled
- resources/geography/game mechanics: disabled

Population capacity is a bounded-compute safety limit, not a fitness rule. Capacity censoring is not death.

## 7. Grounding evidence requirements

For every already-selected ACCEPT/REJECT opportunity, preserve enough evidence to classify the payload path as one of:

- `PROPOSAL_HANDLE_VISIBLE_REFERENCE_DOMAIN`;
- `BASELINE_NO_VISIBLE_PROPOSAL_REFERENCE`.

For handle-treated attempts preserve, in addition to existing cognition evidence:

- exact ordered canonical-ID -> local-handle map;
- raw model-facing handle candidate;
- mapped canonical candidate;
- Gateway canonical intent;
- LawValidator admission result;
- rendered-input/raw-generation/final-evidence ArtifactRefs;
- C10 phase trace;
- snapshot-unchanged proof.

No handle enters canonical simulation state.

## 8. Primary integrity gates

### G0 — static identity/preflight

Before model load:

- execution HEAD equals the frozen execution commit;
- worktree is clean;
- base/tokenizer/adapter/config/runtime identities match exactly;
- parent LIVE and grounding-smoke identities match the frozen source evidence;
- output root does not already exist;
- validate-only performs no model load, generation, or simulation commit.

### G1 — cognition integrity

For every opportunity:

- exactly one score-selector decision;
- frozen C10 FA-prefill -> BASE score phase;
- frozen T=1.0 rule and action order;
- no legality mask;
- WAIT has no payload generation;
- non-WAIT has exactly one payload generation for the already-selected action;
- no retry/fallback/resampling/action rewrite;
- snapshot remains unchanged during cognition;
- weights remain frozen.

### G2 — proposal-handle integrity

For every handle-treated ACCEPT/REJECT payload:

- handle map is deterministic from the compiled visible proposal references;
- only proposal IDs are aliased;
- raw generated `proposal_id` belongs to the visible handle domain;
- mapping resolves to one exact canonical proposal ID from that domain;
- Gateway receives the mapped canonical candidate;
- handles never enter canonical state.

No LawValidator-admission threshold is part of G2.

### G3 — deterministic canonical commit integrity

- all contexts compile before canonical mutation;
- only Gateway-bound, LawValidator-admitted intents may contribute transitions;
- one atomic commit advances each accepted tick boundary;
- state versions/hashes remain monotonic and durable;
- raw model/interface evidence remains noncanonical.

### G4 — persistence/replay integrity

After the run:

- final SQLite boundary loads successfully;
- durable replay reconstructs the same final state hash;
- replay invokes no new cognition;
- required CAS references resolve;
- final evidence can be sealed and hash-verified.

## 9. Descriptive outputs only

Report without behavioral pass thresholds:

- total cognition opportunities;
- selected action distribution overall/by tick/by agent;
- baseline vs handle-treated payload counts;
- handle selections and canonical resolutions;
- Gateway/domain/law rejection counts and reasons where classifiable;
- committed messages;
- proposals created;
- accepts/rejects committed;
- successful births and lineage;
- natural deaths;
- capacity conflicts/censoring;
- population by tick;
- maximum generation depth;
- final population/state hash;
- infrastructure wall time/GPU telemetry.

No minimum birth count is required for integrity pass. A birth, if observed, is a descriptive demonstration of the integrated reproduction path, not a preregistered success threshold.

## 10. Failure policy

After the first model forward:

- never overwrite the evidence root;
- preserve stdout, partial SQLite/CAS, and tick records on any failure;
- diagnose before rerun;
- do not silently change run ID, seed rule, temperature, horizon, lifespan, capacity, context policy, action order, grounding domain, or runtime identity;
- any corrected rerun requires a new versioned evidence root and execution commit.

## 11. Interpretation bounds

A G0-G4 pass establishes only that the score-selected real-model WORLD runtime can integrate proposal-handle reference grounding into a bounded continuous durable multi-agent trajectory without compromising canonical authority or replay integrity.

It does not establish calibrated action availability, correct semantic proposal choice, correct target-agent grounding, reproductive competence, stable population dynamics, evolutionary adaptation, heredity, culture, or civilization.
