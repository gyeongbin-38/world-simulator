# A0 Autonomous Interface Admission v1

**Status:** PRE-REGISTERED / NOT EXECUTED  
**Role:** founder `MOTOR` + `AUTONOMOUS` admission evidence  
**Primary owner:** `specs/experiments/A0-autonomous-interface-admission-v1.yaml`

## Why this study exists

The first real A40 WORLD smoke completed successfully at the infrastructure level, but all six cognition attempts produced token `100257` as the first generated token and stopped with `eos_token` under I0. The exact smoke manifest digest is:

`717bdd81c388c47beb7d5e2777867762b7cd223e61a50f7195840c72315ccf89`

That observation is discovery evidence only. It is not counted in A0's admission denominator.

Inspection of `F0_DATASET_V1` confirmed that FA-v1 was trained for visible-state grounding and for **serialization of an action that had already been selected**. The F0 generator explicitly does not train social policy or autonomous action choice. Therefore A0 does not reopen or retrain Foundation. It tests the minimum model-output interface required to turn a grounded WORLD context into a valid candidate action without adding a social objective.

## Scientific question

> What is the least-intervening output interface under which the exact accepted FA-v1 can reliably emit a valid WORLD action candidate from a real ContextPack, while preserving EXP-000's no-social-prior baseline?

This is an **engineering/scientific admission study**, not an artificial-life outcome experiment. It selects the fixed interface that must be frozen before EXP-000 behavioral observations are interpreted.

## Fixed model and runtime identity

A0 freezes the exact operationally accepted artifact:

- base: `allenai/OLMo-2-0425-1B-Instruct`;
- revision: `48d788eca847d4d7548f375ad03d3c9312f6139e`;
- base checkpoint SHA-256: `36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f`;
- tokenizer digest: `c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff`;
- FA-v1 adapter SHA-256: `46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec`;
- BF16 inference on the A40 deployment path;
- greedy generation, no sampling, retry, fallback, repair, or chat template.

No weight update is permitted in A0.

## Fixed paired context cohort

The cohort uses the already-defined researcher fixture family in `src/alifelm/model/r3_fixtures.py`.

Five context classes are used:

1. `QUIET`
2. `MESSAGE_RECEIVED`
3. `PROPOSAL_RECEIVED`
4. `OWN_PROPOSAL_PENDING`
5. `RECENT_INTERACTION`

There are 16 deterministic cases per class, for 80 compiled ContextPacks. The exact same compiled contexts are reused across all primary treatments. The fixtures alter committed visible state only; they do not contain behavior directives.

The study performs no simulation commit.

## Primary treatments

Treatments are ordered by increasing intervention:

| Treatment | Completion boundary | Constraint |
|---|---|---|
| I0 | none | none |
| I1 | `Action selection JSON:` | none |
| I2 | same neutral boundary | JSON syntax only |
| I3 | same neutral boundary | action-conditional typed JSON |

The promotion rule is **minimal sufficiency**: the first treatment in `I0 -> I1 -> I2 -> I3` that passes both admission gates is the provisional interface.

No treatment says whom to contact, whether to reproduce, whether to cooperate, whether to trust, or what action should be frequent.

## Admission gates

### Motor gate

The output interface must be mechanically reliable:

- codec-valid rate >= 0.99;
- first-token EOS rate <= 0.01;
- evidence completeness = 1.00;
- infrastructure failures = 0;
- one exact greedy repeat must be byte/token identical.

### Autonomous gate

The candidate must also bind to the real WORLD domain:

- Motor gate passes;
- domain-valid rate >= 0.95;
- every context class has domain-valid rate >= 0.90.

These gates constrain **validity**, not preference.

There is deliberately no required rate for WAIT, SEND, PROPOSE, ACCEPT, or REJECT. A population that chooses `NO_DIRECTED_ACTION` very often may be scientifically uninteresting, but it is not thereby interface-invalid. Conversely, first-token EOS is not reinterpreted as WAIT because it is not a canonical action choice.

## I3 branch-order firewall

If I3 is the first primary treatment that passes, it is not immediately admitted. Four preregistered permutations of the typed branch order are run over the same 80 contexts.

I3 passes this audit only if:

- every order separately passes the primary gates;
- >= 95% of contexts have identical parsed candidate action labels across all four orders;
- the spread of domain-valid rates across orders is <= 0.05.

This prevents a JSON-schema branch ordering artifact from becoming an accidental behavioral prior.

## Secondary diagnostics

Existing researcher-only diagnostics remain available but do not participate in primary promotion:

- I-05R3 full action-label sequence scoring;
- I-05R4 balanced opaque selector codebooks;
- forced handle-grounding diagnostics.

They are used only if A0 fails or exposes an interface-bias mechanism. A new treatment, threshold, or prompt wording requires an A0 v2 preregistration. A0 v1 must not be rewritten after results are observed.

## EXP-000 firewall

A0 must not introduce:

- personality assignments;
- trust/friend/enemy variables;
- social-desirability prompts;
- mate or fitness scores;
- survival/cooperation objectives;
- target action frequencies;
- examples demonstrating preferred social behavior.

The selected interface is frozen **before** EXP-000 behavioral results are used. Main EXP-000 behavior must never be used to tune the interface and then be reported as if the interface had been fixed in advance.

## Interpretation

A0 can establish that an output interface is sufficiently reliable for founder admission. It cannot establish that:

- FA-v1 is a formally promoted training recipe;
- any particular social behavior is desirable or correct;
- the founder model is free of pretrained social priors;
- EXP-000 has passed behavioral validation;
- Founder Freeze is complete.

After A0, its immutable evidence must be reviewed and the founder admission record updated explicitly. Only then may the admission sequence advance.
