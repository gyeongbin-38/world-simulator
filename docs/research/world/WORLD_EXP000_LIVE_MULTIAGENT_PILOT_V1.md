# WORLD EXP-000 Live Multi-Agent Pilot V1

Status: **PREREGISTERED / NO PILOT MODEL FORWARD YET**

## 1. Purpose

This is the first bounded continuous LIVE EXP-000 run using the real accepted WORLD model path together with the deterministic score-selector, existing simulation kernel, durable SQLite state, CAS evidence, and read-only researcher observation.

The scientific/engineering question is deliberately narrow:

> Can multiple real-model agents participate in one continuous, durably recorded WORLD trajectory under the frozen score-selector architecture without introducing retries, fallback actions, hidden social objectives, or researcher-authored action-frequency targets?

This pilot is not an admission test for social intelligence, reproductive competence, culture, evolution, civilization, or Founder Freeze. Behavior counts are descriptive only.

## 2. Frozen source evidence

The pilot is authorized by the preceding bounded evidence chain:

- P2 result: `C10_NOT_BEHAVIORALLY_ADMITTED`
- P2-D1 details SHA-256: `0e5e62709d58168c9922645c1d05d54a7f5c417b68b3f461b4558d3706ca3b17`
- P2-D4 result digest: `e7a7bfae9ecaaebf862727ed31b228be921ea6a4ac889520b6361279c3ad76d6`
- score-selector pilot preregistration commit: `0c10b121695a31000f9d1f675d7fb3c5378fc248`
- generic selector implementation: `0efa0aecd600689fc2593880513623e2a1a9693b`
- score-selected runtime composition: `59d944aa4d6b25f7ef9505f1a7c6c777ab797922`
- C10 real-runtime adapter: `fa2423899f779dbeb16838dfe4c9ddd4e9037027`
- A40 smoke execution commit: `769cf611cda535a8b590d5c826b90ca505deaac6`
- A40 smoke result digest: `7e69dbc2c40509f0cc6f10906a5482cc4cc2d01a8a114e66cb836e72ff95a912`
- A40 smoke canonical archive SHA-256: `d60225464d8c89dea55fad82fc977895fb69bdd597ee6e0882e0ced2789817f2`
- A40 smoke off-machine archive/hash verification: PASS

The A40 smoke showed exact live reproduction of the frozen D1 C10 mean-score vector for the preregistered fixture, deterministic selection of `SEND`, valid forced-SEND payload generation, Gateway binding, descriptive LawValidator admission, no snapshot mutation, no state commit, no weight update, and no retry/fallback/repair.

## 3. Frozen model/runtime identity

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

Each cognition opportunity uses the preregistered score-selector V1:

1. compile the ContextPack from one committed snapshot;
2. WORLD prefill under FA-v1;
3. switch to BASE for the frozen D1/I3 five-action branch score measurement;
4. use each action's **mean branch log probability**;
5. apply the frozen `T=1.0` softmax without any per-action correction;
6. derive the deterministic categorical variate from `WORLD_EXP000_SCORE_SELECTOR_V1|<run_id>|<tick>|<opportunity_id>|<agent_id>` via SHA-256;
7. freeze the selected action label;
8. for non-WAIT actions, run exactly one forced-I3 payload generation for that selected action only;
9. bind identity through `CognitionGateway`;
10. validate against the immutable snapshot with `LawValidator`;
11. commit only validated transition fragments through the deterministic commit barrier.

There is no legality mask, retry, fallback, repair, action bonus, action-frequency target, hidden target injection, social reward, or post-selection action rewrite.

A selected mechanically unavailable action may be rejected by the existing Gateway/domain/law path. It is not resampled and does not silently become WAIT.

## 5. Frozen run configuration

- run ID: `WORLD_EXP000_LIVE_PILOT_V1_R1`
- founders: `EXP000_FOUNDER_A`, `EXP000_FOUNDER_B`, `EXP000_FOUNDER_C`
- founder count: `3`
- horizon: `20` ticks
- fixed lifespan: `20` ticks
- maturity delay: `0` ticks
- refractory interval: `0` ticks
- population capacity: `6`
- context policy: existing `exp000-context` v1.0.0
- max prior visible records: `2`
- same-tick peer outputs: not visible
- batching: disabled
- generation sampling: disabled for payload generation; greedy typed branch completion
- score-selector temperature: `1.0`
- score-selector stochasticity: deterministic opportunity-identity hash only
- neural heredity: disabled
- resources: disabled
- geography: disabled
- game mechanics/UI authority: disabled

The population capacity of 6 is a pre-execution bounded-compute safety limit, not an agent preference or fitness rule. Any capacity censoring must be recorded separately and must never be counted as agent death.

## 6. Durable execution boundary

The run must use `SQLiteReferenceStore` plus filesystem CAS evidence.

For every committed tick, preserve at minimum:

- tick and state version before/after;
- previous/resulting state hashes;
- ContextPack ArtifactRefs;
- score-selector decision evidence per cognition opportunity;
- selected action and exact score vector/probabilities;
- selector seed digest and exact uniform fraction;
- payload raw generation/final cognition evidence for each non-WAIT selection;
- parser/Gateway/domain/law outcomes;
- committed messages;
- reproduction proposals;
- accept/reject results;
- births and parent IDs in canonical lineage evidence;
- natural deaths;
- capacity conflicts/censoring;
- commit events and CAS references.

Researcher observation is read-only and cannot mutate or advance simulation truth.

## 7. Primary integrity gates

### G0 — static identity/preflight

Pass only if, before model loading:

- repository HEAD equals the frozen execution commit;
- worktree is clean;
- base/tokenizer/adapter/config/runtime hashes exactly match the frozen identities;
- A40 smoke source result/archive identities match this preregistration;
- SQLite/CAS output locations do not already contain a conflicting run;
- no model load or generation occurs in validate-only mode.

### G1 — per-opportunity cognition integrity

For every enumerated cognition opportunity:

- exactly one score-selector decision is produced;
- the C10 phase identity is FA prefill -> BASE scoring;
- frozen five-action order and T=1.0 rule are unchanged;
- WAIT causes no payload-generation attempt;
- non-WAIT causes exactly one payload-generation attempt for the already-selected action;
- payload stage cannot re-select another action;
- rejection causes no retry/fallback/resampling;
- bound snapshot remains unchanged during cognition;
- model weights remain frozen.

### G2 — deterministic canonical commit integrity

For every tick boundary:

- all ContextPacks are compiled before canonical mutation;
- only Gateway-bound and LawValidator-admitted intents can plan canonical transitions;
- model completion order cannot publish state;
- exactly one atomic commit advances the accepted boundary;
- resulting state version increases monotonically;
- durable state hash agrees with the materialized snapshot;
- raw model text remains CAS/evidence, not canonical state.

### G3 — persistence/replay integrity

After the bounded run:

- the SQLite durable run loads at the final committed boundary;
- durable replay reconstructs the same final state hash;
- replay invokes no new model cognition;
- CAS references required by committed evidence resolve successfully;
- canonical evidence/manifest is sealed and hash-verified before any follow-up pilot.

## 8. Descriptive trajectory outputs

Report, without pass/fail thresholds:

- total cognition opportunities;
- selected action distribution overall and by tick;
- selected action distribution by visible context category where available;
- candidate/intent/domain/law rejection counts;
- committed messages and message bodies as evidence references/text projections;
- proposals created;
- accepts and rejects;
- successful births;
- capacity-censored births/conflicts;
- natural deaths;
- population by tick;
- generation depth and lineage graph;
- per-agent action sequence;
- final population and state hash;
- run wall time and GPU memory telemetry as infrastructure metadata.

No minimum number of SEND, PROPOSE, ACCEPT, births, deaths, or non-WAIT actions is a primary gate. An all-WAIT trajectory may still satisfy infrastructure integrity, though it would be behaviorally uninteresting and reported as such.

## 9. Failure policy

After the first pilot model forward:

- never overwrite the evidence root;
- never silently modify a threshold, seed rule, temperature, capacity, horizon, lifespan, context policy, action order, or runtime identity;
- preserve stdout and partial durable state/evidence on any failure;
- diagnose before any rerun;
- a corrected rerun requires a new versioned evidence root and execution commit.

No post-hoc action-frequency target may rescue or invalidate the primary integrity gates.

## 10. Interpretation bounds

A G0-G3 pass establishes only that the frozen real-model score-selector architecture can operate as a bounded, continuous, durable multi-agent artificial-life trajectory under the existing deterministic laws.

It does not establish:

- calibrated action probabilities;
- social intelligence;
- reproductive competence;
- beneficial cooperation;
- stable population dynamics;
- evolutionary adaptation;
- neural heredity;
- culture or language evolution;
- civilization formation;
- Founder Freeze.

Those require separately preregistered studies.
