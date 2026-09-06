# WORLD EXP-000 Score-Selector A40 Smoke V1

Status: **PREREGISTERED / NO NEW MODEL FORWARD YET**

## 1. Purpose

This is a deployment/integration smoke for the preregistered EXP-000 score-selector pilot. It is not a behavioral-admission study and its fixture is intentionally selected to exercise the non-WAIT conditional-payload path.

The smoke asks only whether the exact frozen C10 score path can be composed on the accepted A40 runtime as:

`FA WORLD prefill -> BASE five-branch scoring -> V1 deterministic categorical selector -> selected SEND payload generation -> CognitionGateway binding`

No canonical simulation commit is required by this smoke.

## 2. Frozen source identities

- parent pilot preregistration: `WORLD_EXP000_SCORE_SELECTOR_PILOT_V1`
- parent pilot preregistration commit: `0c10b121695a31000f9d1f675d7fb3c5378fc248`
- generic selector CPU admission implementation: `0efa0aecd600689fc2593880513623e2a1a9693b`
- score-selected runtime CPU composition implementation: `59d944aa4d6b25f7ef9505f1a7c6c777ab797922`
- C10 real-runtime adapter CPU implementation: `fa2423899f779dbeb16838dfe4c9ddd4e9037027`
- P2-D1 details SHA-256: `0e5e62709d58168c9922645c1d05d54a7f5c417b68b3f461b4558d3706ca3b17`
- P2-D4 result digest: `e7a7bfae9ecaaebf862727ed31b228be921ea6a4ac889520b6361279c3ad76d6`

Accepted model/runtime identity remains the frozen WORLD identity:

- base: `allenai/OLMo-2-0425-1B-Instruct`
- base revision: `48d788eca847d4d7548f375ad03d3c9312f6139e`
- base checkpoint SHA-256: `36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f`
- FA-v1 adapter SHA-256: `46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec`
- adapter config SHA-256: `687100a0b6340b6096ca1e86066d3c13224b3c8e14ce9fb1b0cf78a52a8bdb7d`
- tokenizer aggregate SHA-256: `c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff`
- canonical runtime pip-freeze SHA-256: `a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf`

## 3. Offline fixture-selection procedure

Before this smoke was preregistered, and before any new model forward after the parent pilot preregistration, the already-recorded P2-D1 C10 mean-score vectors were passed through the already-CPU-admitted V1 deterministic selector for all 160 frozen R3 contexts.

Observed source-only selector result:

- non-WAIT fixtures: `80 / 160`

The smoke fixture is the first preferred SEND fixture from that offline enumeration. This selection is deliberately conditioned on exercising the payload path; therefore the smoke action itself is **not** evidence of behavioral frequency, context sensitivity, or social competence.

## 4. Frozen smoke fixture

- context class: `QUIET`
- case index: `4000`
- run ID: `i05r3-quiet-4000`
- tick: `2`
- actor: `A`
- opportunity ID: `cbf8914977ebb729ac940ee5cdcdecf23fc0680c99797cb2b1694b7c1b052daf`
- selected action from frozen source scores: `SEND`
- selector seed digest: `91b37369db308547a211fd40ee5c6d01f5bf632bc125a30fd46bed3915f0e227`
- exact uniform numerator: `131804850447753180354580172813106518111693388313251446682588685379011516417103`
- exact uniform denominator: `231584178474632390847141970017375815706539969331281128078915168015826259279872`
- human-readable `u`: approximately `0.569144452422906`

Offline source-score categorical masses at frozen `T=1.0`:

- WAIT: `0.562304830673132`
- SEND: `0.3417218941235785`
- PROPOSE: `0.04752904420760531`
- ACCEPT: `0.043275687217514326`
- REJECT: `0.0051685437781698726`

No alternate fixture may replace this one after the first new model forward. If the smoke fails, preserve the failed evidence and diagnose the failure; do not search for another passing fixture.

## 5. Frozen smoke gates

### S0 — static admission

Before model loading:

- repository HEAD must equal the frozen smoke execution commit;
- worktree must be clean;
- exact base/tokenizer/adapter/config hashes must pass the existing static deployment verifier;
- canonical runtime freeze must match;
- P2-D1 details file must exist and have the frozen SHA-256;
- the exact `(QUIET, 4000)` source row must resolve to the frozen run/tick/actor/opportunity identity;
- applying V1 selection to the source row must reproduce `SEND`, the frozen seed digest, and the exact uniform fraction;
- validate-only mode must perform no torch/CUDA import and no model load.

### S1 — live C10 score reproduction

On A40 execute mode:

- one accepted base+FA runtime is loaded;
- the frozen ContextPack is compiled once;
- C10 scoring is exactly `prefill_adapter=True`, `selector_adapter=False`;
- the five live mean branch scores must equal the frozen P2-D1 source row scores exactly;
- selector decision must reproduce `SEND` and the frozen seed identity;
- bound Snapshot hash must not change during score measurement.

A score mismatch is an infrastructure/scientific-identity failure, not permission to relax tolerance post hoc.

### S2 — selected payload path

After `SEND` is fixed:

- one forced-SEND I3 payload generation is allowed;
- payload generation must retain C10 phase identity;
- WORLD context must not be recomputed after the adapter switch inside that generation path;
- generated candidate must keep the selected action label and required SEND payload field shape;
- malformed or mismatching output is a typed rejection, never re-selection or fallback;
- no retry, repair, legality mask, action bonus, or hidden target injection is allowed.

### S3 — Gateway/evidence integrity

- `CognitionGateway` remains sole authority for actor/tick/intent identity;
- if a candidate is present, Gateway binding must complete or produce a typed model/domain rejection through the existing boundary;
- raw generation and final cognition evidence must be CAS-addressable;
- selector score vector, probabilities, seed digest, exact `u`, selected action, payload parse status, phase trace, and Gateway result are written to the immutable smoke result manifest;
- simulation-state commits = `0`;
- model weight updates = `0`.

The smoke may report later LawValidator admissibility descriptively, but no post-hoc social/activity threshold is introduced.

## 6. Pass interpretation

`INFRASTRUCTURE_PASS` means only that the frozen score-selected C10 inference path works end-to-end for the intentionally non-WAIT smoke fixture with exact source-score reproduction and durable evidence.

It does not establish autonomous behavioral competence, social intelligence, communication quality, reproductive competence, activity frequency, or Founder Freeze.

Only after this smoke passes may the separately preregistered bounded `3 founders x 20 ticks` LIVE EXP-000 score-selector pilot be executed.