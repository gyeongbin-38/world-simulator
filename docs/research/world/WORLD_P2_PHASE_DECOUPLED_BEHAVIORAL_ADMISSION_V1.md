# WORLD P2 Phase-Decoupled Behavioral Admission V1

Status: PREREGISTERED / IMPLEMENTATION NOT YET ADMITTED

Study ID: `WORLD_P2_PHASE_DECOUPLED_BEHAVIORAL_ADMISSION_V1`

## 1. Scientific question

P1C-v2 identified `FA→BASE` as the strongest phase-decoupled architecture candidate under teacher-forced action-label scoring. P2 asks a separate behavioral question:

> When the model must actually generate a complete typed `ActionIntent` under the previously admitted I3 interface, does `FA→BASE` produce mechanically valid, deterministic, context-sensitive autonomous candidates without relying on FA-v1 during action selection?

P2 is a dry-run behavioral admission study. It does not commit simulation state and does not evaluate social desirability, cooperation, mating preference, fitness, friendship, leadership, rank, civilization, or any other researcher-defined social objective.

## 2. Source evidence frozen before P2

P2 is motivated by, but must not rewrite, the frozen P1C-v2 evidence:

- P1C-v2 results commit: `1059b03e28668e2b8563c4aa81d39e1a2e65576f`
- P1C-v2 execution commit: `4fcbf4827a2887700dc59e180a7c08e5117b59b9`
- P1C-v2 result digest: `0e19ae757ee07121102e1bd278125fe41d92e55b30add75f1e5895a1c315df04`
- P1C-v2 summary SHA-256: `8632473c2e13983d535a8b16381b3f8e4dc1eea68741ccb0ad2e9cfd4ef1c40a`
- P1C-v2 details SHA-256: `c03e4370cf077c0c7c492727375141ecb66623762bcc96b0881ae147c5a272ea`
- P1C-v2 stdout SHA-256: `061d50db2eb7dec80af44c251bf5586c13df64f1a8a486e530ab693a7800e004`
- P1C-v2 canonical archive SHA-256: `b34f60b98868bf9a26b3d726fb4b6fd9093e9d2ec462b247cb82553900b0c39d`

The frozen P1C-v2 conclusion was bounded: `FA→BASE` preserved robust proposal/ownership structural signal, reduced WAIT margin relative to `FA→FA`, and uniquely passed the latent rank-1 sensitivity diagnostic. It did not establish autonomous behavioral competence.

## 3. Frozen model identity

P2 uses the same accepted WORLD model identity:

- base: `allenai/OLMo-2-0425-1B-Instruct`
- base revision: `48d788eca847d4d7548f375ad03d3c9312f6139e`
- base checkpoint SHA-256: `36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f`
- FA-v1 adapter SHA-256: `46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec`
- FA-v1 adapter config SHA-256: `687100a0b6340b6096ca1e86066d3c13224b3c8e14ce9fb1b0cf78a52a8bdb7d`
- tokenizer digest: `c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff`
- tokenizer/config aggregate: `eeed26d20a24ad35479aa33b690b196096c5f98fee8bc43d816c3bd314987c38`

Canonical runtime requirements remain the existing 60-package BF16 A40 environment with pip-freeze SHA-256:

`a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf`

No weight update, retraining, merge, quantization change, tokenizer change, or model substitution is permitted in P2.

## 4. Fresh held-out cohort

P2 uses a fresh deterministic R3 cohort that has not been used by P1, P1B, P1C-v1, D1, or P1C-v2 primary measurements:

- fixture compiler: `compile_r3_fixture`
- case indices: `4000..4031` inclusive
- matched cases: `32`
- context classes per case: `5`
- total contexts per condition: `160`

Frozen context classes:

1. `QUIET`
2. `MESSAGE_RECEIVED`
3. `PROPOSAL_RECEIVED`
4. `OWN_PROPOSAL_PENDING`
5. `RECENT_INTERACTION`

The exact compiled context bytes for one `(context_class, case_index)` must be identical across all P2 phase conditions and all branch-order audit runs.

## 5. Frozen phase conditions

P2 generates behavior under all four common-topology phase conditions; no condition may use ordinary full-sequence generation as a primary measurement.

- `C00`: BASE prefill → BASE selector/generation
- `C01`: BASE prefill → FA selector/generation
- `C10`: FA prefill → BASE selector/generation
- `C11`: FA prefill → FA selector/generation

For every attempt:

1. Phase A executes the exact WORLD context once under the frozen prefill adapter state.
2. The Phase A `past_key_values` cache is retained without recomputing WORLD context.
3. Phase B begins at the exact I3 completion suffix under the frozen selector adapter state.
4. The selector state remains fixed for the entire generated JSON continuation.
5. Candidate generation is greedy and deterministic.

P2 is an operational phase decomposition. It does not claim pure module-level causal isolation inside the transformer.

## 6. Frozen interface and generation policy

P2 reuses the previously admitted I3 conditional typed codec without semantic narrowing.

I3 identity:

- treatment ID: `i05r2-i3-conditional-typed-codec`
- version: `1.0.0`
- completion suffix: `\nAction selection JSON:\n`
- constraint policy: `i05r2-conditional-typed-action-json-v1`

The typed schema may constrain JSON structure and action-conditional payload fields, but must not constrain semantic payload values beyond the existing I3 schema. In particular, P2 must not dynamically enumerate a preferred target, proposal ID, action, message body, or context-specific desired behavior.

Generation policy:

- greedy decoding
- `do_sample = false`
- `max_new_tokens = 128`
- seed: `35020260831`
- temperature: none
- top-p: none
- top-k: none
- repetition penalty: `1.0`
- no retry
- no fallback
- no repair
- no EOS suppression
- no `min_new_tokens`
- no scalar action-logit correction
- no action hint
- no action-frequency target

The generated continuation is evaluated by the existing typed codec/domain/commit diagnostic boundary. A generated candidate remains non-canonical; P2 never commits it to simulation state.

## 7. Primary measurements

For every condition and every context P2 records at minimum:

- exact rendered/context bytes digest;
- context/prefix token IDs;
- adapter state for Phase A and Phase B;
- generated token IDs and raw text CAS reference;
- finish reason;
- first-token EOS indicator;
- parse status;
- codec validity;
- domain validity;
- commit validity diagnostic;
- generated candidate action label when available;
- domain-valid intent kind when available;
- evidence completeness;
- infrastructure failure count.

Action distributions are reported descriptively only. No action frequency is a pass/fail target.

## 8. G0 — integrity gate

`P2-G0` passes only if all of the following hold:

- exact frozen base, tokenizer, adapter, config, runtime, preregistration, and P1C-v2 source-evidence identities are verified before inference;
- all four conditions contain exactly 160 primary attempts;
- compiled context bytes and tokenization are identical across conditions for every matched fixture;
- each attempt performs exactly one WORLD-context prefill;
- Phase A is not recomputed after the adapter-state switch;
- phase adapter flags are exactly `C00`, `C01`, `C10`, `C11` as frozen above;
- the I3 treatment and schema identity are unchanged;
- the first primary attempt of every condition is repeated once after the condition and is byte-identical in raw generated text, token IDs, finish reason, and frozen identities;
- runtime freeze remains exact;
- source P1C-v2 evidence hashes are unchanged before versus after execution;
- generation calls are research dry runs only;
- simulation state commits = `0`;
- model weight updates = `0`;
- retries/fallbacks/repairs = `0`.

If G0 fails, all behavioral attribution gates are `NOT_EVALUABLE`. No tolerance may be relaxed post hoc.

## 9. G1 — C10 motor/domain admission

`P2-G1` evaluates only the candidate condition `C10` and reuses the previously frozen A0 interface-capability thresholds rather than inventing new thresholds after observing P2 data.

Required:

- codec-valid rate ≥ `0.99`;
- first-token EOS rate ≤ `0.01`;
- evidence-complete rate = `1.0`;
- infrastructure failures = `0`;
- exact repeat = true;
- domain-valid rate ≥ `0.95`;
- minimum per-context-class domain-valid rate ≥ `0.90`.

Commit-valid rate and commit-status counts are reported, but canonical simulation commit is forbidden.

Passing G1 means only that C10 can cross the existing mechanical interface boundary at the preregistered rate. It does not establish a good social policy.

## 10. G2 — C10 generated context sensitivity

`P2-G2` asks whether complete generated candidate actions vary with context under C10 without defining which social action should be preferred.

Two frozen criteria are reused from the P1/P1B sensitivity diagnostic:

1. **Matched sensitivity rate**
   - one matched case is counted sensitive only when all five context outputs are domain-valid and at least two generated action labels differ across the five contexts;
   - denominator = all 32 matched cases;
   - required rate ≥ `0.25`.

2. **Distributional sensitivity from QUIET**
   - generated action labels are compared by total-variation distance between each non-QUIET class and `QUIET`;
   - a domain-invalid attempt is represented by an `INVALID` sentinel rather than silently dropped;
   - because G1 separately requires ≥0.90 domain validity in every context class, invalidity alone cannot satisfy a TVD threshold of `0.25`;
   - TVD threshold = `0.25`;
   - at least `2` of the `4` non-QUIET classes must meet or exceed the threshold.

G2 passes only if both criteria pass.

No required WAIT, SEND, PROPOSE, ACCEPT, or REJECT frequency exists.

## 11. G3 — C10 I3 branch-order robustness

Context sensitivity is not interpretable if JSON-schema branch order determines the generated action. Therefore, if and only if G0, G1, and G2 pass, P2 runs the existing four frozen I3 branch orders on the complete C10 cohort as a conditional audit. These audit runs never replace primary C10 observations.

Frozen branch orders:

1. `WAIT, SEND, PROPOSE, ACCEPT, REJECT`
2. `REJECT, ACCEPT, PROPOSE, SEND, WAIT`
3. `SEND, PROPOSE, ACCEPT, REJECT, WAIT`
4. `ACCEPT, WAIT, REJECT, SEND, PROPOSE`

The audit reuses the A0 branch-order thresholds:

- every branch order must independently satisfy the G1 motor/domain thresholds;
- generated candidate-label agreement across the four orders ≥ `0.95` over the complete 160-context cohort;
- domain-valid-rate spread across orders ≤ `0.05`.

`P2-G3` passes only if all three requirements pass.

If G0/G1/G2 fails, G3 is `NOT_RUN_BY_PROTOCOL`, not a failure disguised as missing data.

## 12. Comparator measurements

`C00`, `C01`, and `C11` are measured on exactly the same primary cohort and interface. For each comparator, P2 reports the same G1-style validity metrics and G2-style generated sensitivity metrics, but comparator outcomes do not alter the preregistered C10 admission thresholds.

The following are descriptive diagnostics only, with no pass/fail threshold:

- action-label distributions by condition and context;
- WAIT rate by condition and context;
- paired C11→C10 WAIT escape/reversal counts;
- C10 versus C00/C01/C11 matched action-label agreement;
- commit-status distributions;
- generated-token-count distributions.

These diagnostics may explain a result but cannot rescue a failed primary gate.

## 13. G4 — candidate promotion rule

`P2-G4` is the bounded phase-decoupled behavioral admission decision.

`C10_PHASE_DECOUPLED_BEHAVIORAL_ADMISSION_PASS` requires:

- `P2-G0 = PASS`
- `P2-G1 = PASS`
- `P2-G2 = PASS`
- `P2-G3 = PASS`

Otherwise the candidate is not behaviorally admitted under P2.

A G4 PASS means only that the exact C10 architecture is a mechanically valid, context-sensitive, schema-order-robust dry-run candidate under the frozen R3 fixture family. It does not establish open-world social competence, long-horizon autonomy, deployment suitability, or Founder Freeze.

## 14. Forbidden post-observation changes

After the first P2 model forward, none of the following may be changed for the primary study:

- cohort indices or context classes;
- phase conditions;
- I3 suffix or schema;
- generation policy;
- G0/G1/G2/G3/G4 thresholds;
- validity definitions;
- treatment order;
- adapter/base/tokenizer/runtime identities;
- retry/fallback/repair policy;
- action-frequency requirements;
- semantic payload constraints.

If implementation failure occurs after inference has begun, preserve the failed evidence root and stdout. Any corrected rerun must use a new versioned evidence root and a new execution commit; failed evidence may not be overwritten.

## 15. Interpretation bounds

P2 may establish only the bounded behavioral admission defined above.

P2 cannot establish:

- that FA-v1 is globally policy-neutral;
- that BASE is an optimal or generally capable social-policy model;
- that generated actions are socially desirable;
- that one action frequency is correct;
- that long-horizon emergent behavior will occur;
- that multi-agent dynamics are stable;
- that reproduction, inheritance, ecology, resources, affect, culture, or civilization mechanisms are validated;
- Founder Freeze.

Founder Freeze remains `NOT_ESTABLISHED` unless established by a separate explicit future experiment.

## 16. Execution order

The frozen execution order is:

1. static validation only;
2. G0 preflight identities and fresh-cohort compilation;
3. primary `C00` 160 attempts + one exact repeat;
4. primary `C01` 160 attempts + one exact repeat;
5. primary `C10` 160 attempts + one exact repeat;
6. primary `C11` 160 attempts + one exact repeat;
7. evaluate G0/G1/G2;
8. if G0/G1/G2 pass, execute the four full-cohort C10 branch-order audit runs and evaluate G3;
9. evaluate G4;
10. write immutable summary/details evidence;
11. preserve stdout and create a canonical archive before any post-hoc inference.

No result-dependent model or interface modification is permitted inside this sequence.