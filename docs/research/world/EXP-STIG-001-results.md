# EXP-STIG-001 results

Status: R2 is permanently recorded as PROTOCOL-CENSORED / NO SCIENTIFIC EFFECT ESTIMATE; R3 is a separate constrained-codec operational replication.

The first execution (`EXP_STIG_001_V1`) is retained as
`CENSORED_NO_SCIENTIFIC_RESULT`: 12 complete responses, zero commits, and a
300-second transport timeout. Its action contents were not scored and it is
not pooled with R2.

## R2 evidence

The fresh matched cohort completed 9 worlds (three blocks × A/B/C), four ticks,
and 108 primary opportunities. The immutable result receipt is
`E:/WORLD/AI_CACHE/evidence/EXP_STIG_001_R2/result.json`, manifest digest
`ebb1b7d4b40fd25b5bdc7e8647e3b607be0ce5564ae21a69ab276feffbd1fa8e`.
The independent observer analysis is
`observer-analysis.json` (SHA-256
`668ed2e631caa9f328a205ff61f1800c68f592e14e9c121115da0a25d2d9e060`).

| condition | opportunities | accepted | rejected | foreign trace uses | register changes |
|---|---:|---:|---:|---:|---:|
| A message only | 36 | 0 | 36 | 0 | 0 |
| B persistent trace | 36 | 0 | 36 | 0 | 0 |
| C causal world | 36 | 0 | 36 | 0 | 0 |

All 108 outputs failed strict JSON parsing with extra data after the model
completion. Therefore no model-chosen WAIT, communication, trace creation,
reuse, register change, or causal counterfactual exposure occurred. This is a
codec/model-output limitation, not a social-behavior observation.

The preregistered paired differences are zero in every block:
B−A environment-use rate = 0 and C−B environment-use rate = 0. There were no
eligible counterfactual probes and no attributable chains. The R2 result JSON
contains the runner's operational S0 field, but because every output was
protocol-rejected, R2 is PROTOCOL-CENSORED and provides NO SCIENTIFIC EFFECT
ESTIMATE; it is not evidence that persistent traces have no value.

Costs were 108 requests, 21,036 prompt tokens, 13,824 generated tokens, and
11,009.31 wall seconds. OLMo Q8 supplied 72 opportunities and Villanova Q8 36;
both model files and the llama.cpp executable are hash-bound in `planned.json`.

Deterministic/fault/replay validation passed before inference; the independent
runner audit and read-only notebook audit passed afterward. Raw model text and
timing evidence remain in CAS and do not enter canonical state. No EXP-000 or
Campfire code was changed. Four ticks and zero accepted actions cannot identify
specialization, general task utility, duplicated-work reduction, or population
effects.

The full machine-readable provenance is
`specs/experiments/EXP-STIG-001-results-v1.yaml`.


## R3 constrained codec

R2 raw evidence and manifests remain unchanged and the R2 audit still passes
(manifest digest ebb1b7d4b40fd25b5bdc7e8647e3b607be0ce5564ae21a69ab276feffbd1fa8e).
The R2 scientific record remains PROTOCOL-CENSORED / NO SCIENTIFIC EFFECT
ESTIMATE because all 108 strict parses failed on trailing model material.

A fresh, six-generation qualification using both frozen Q8 models and all
A/B/C interfaces passed: 6/6 completed, 6/6 exactly-one-object,
6/6 strict-parser-valid, 0 generation/runtime failures, and 0 parser failures.
There were four semantic Gateway rejections (placeholder trace/peer data);
these are recorded separately from codec validity. Qualification manifest
digest: 77a903ce5086d5636c430ce4e21ad481f591034c5614de3a71318c0ce4333600.

R3 then executed the unchanged 9-world, four-tick, 108-primary-request
comparison with the generation-side grammar. The immutable R3 result is
E:/WORLD/AI_CACHE/evidence/EXP_STIG_001_R3_RUN2/result.json, manifest digest
2e51e173c99a7bfa0acd9760f8f5da2ee2f323f9a08fb91073e769fc2a7b09c9.
All 108 model outputs were parser-valid single objects: 36 semantic WAIT
intents were accepted in condition A; 72 REUSE intents in B/C were rejected by
the Gateway because trace_id was not visible. No SEND, TRACE, or SET intent
was generated, no protocol/runtime failure occurred, and no counterfactual
exposure or attributable chain existed. Paired B-A and C-B environment-use
rates were zero in every block; the separate R3 operational interpretation is
S0 - no demonstrated difference. R3 response metadata records the
constraint policy ID and per-condition grammar hashes; exact decoded raw
outputs are retained in CAS.

## R4 grounded action affordance

R4 is a new interface version; R2 and R3 evidence remain unchanged. R4 derives
the generation grammar from each actor's current visible state. In B/C, REUSE is
omitted when no committed trace exists, and opaque targets/trace IDs are
enumerated from the visible state. Each opportunity stores the exposed action
set, visible references, state/context version, affordance hash, and grammar
hash.

The semantic-affordance qualification passed in
E:/WORLD/AI_CACHE/evidence/EXP_STIG_001_R4_qualification_pass2/qualification.json:
12/12 completed generations, 12/12 strict-parser-valid, 12/12
affordance-valid, 12/12 Gateway-valid, and all representative-state invariant
checks passed. The qualification manifest digest is
9655afd9f87883fb746270db709acac0350c6c2457c302ccfe666f51334e4bcb.

The matched R4 execution completed 9 worlds, four ticks, and 108 primary
opportunities using the unchanged A/B/C treatments. All 108 candidates were
parser-valid and affordance-valid; 102 were Gateway-valid and committed, while
six C-condition SET candidates were rejected by same-boundary register
conflicts. Actions were WAIT 53, SEND 45, SET 10, TRACE 0, and REUSE 0.
There was no spontaneous trace bootstrap, no trace reuse, no counterfactual
exposure, and no attributable stigmergic chain. The three C worlds each
committed one register change. The R4 result audit passed with manifest digest
409409e8006b68d263b4a67f5678fe6bb537796a5f0d2565c9725320fb53c944.
This is an operational S0 result for this run: the grounded interface removed
the prior impossible-reference defect, but no persistent trace was created.
