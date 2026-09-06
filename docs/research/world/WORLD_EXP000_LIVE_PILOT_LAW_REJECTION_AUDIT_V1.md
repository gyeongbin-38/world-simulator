# WORLD EXP-000 Live Pilot Law-Rejection Audit V1

Status: **READ-ONLY AUDIT COMPLETE / NO NEW MODEL FORWARD**

## 1. Scope

This record classifies the eight `LawValidator` rejections observed in the sealed and off-machine-hash-verified `WORLD_EXP000_LIVE_PILOT_V1_R1` trajectory. It is a read-only post-run audit over the immutable tick records; no model forward, replay cognition, state mutation, threshold change, or corrective rerun was performed.

Source live result identity:

- execution commit: `55b4c5128a40c2e68a6a7cc205424e7e6a802314`
- live result digest: `b82267d7769cbc4dc56aaa3c5f82e5e66b1b669ef407b4c58d1a994b4ae29f00`
- manifest SHA-256: `8c239e0c3550ec435ccd8ef2a718845a88d623d43cdcb7151d0b11825768e4e2`
- canonical archive SHA-256: `b9d6e31df6e01e1ddabd943b40601255c7d80361b3eb5b3c217f25f5cc5b36e3`
- off-machine destination hash verification: PASS

## 2. Accounting

Across 60 cognition opportunities:

- selected: `WAIT=26`, `SEND=17`, `PROPOSE=10`, `ACCEPT=6`, `REJECT=1`
- law admitted: `WAIT=26`, `SEND=16`, `PROPOSE=10`, `ACCEPT=0`, `REJECT=0`
- law rejections: `8`
- parse/payload rejections before the law boundary: `0`

The read-only classifier reproduced the manifest count exactly: `8 / 8` law rejections accounted for.

## 3. Rejection classes

Observed rejection reasons:

- `SELF_TARGET`: `1`
- `UNKNOWN_PROPOSAL_ID`: `7`

By action:

- `SEND`: `1` rejected
- `ACCEPT`: `6` rejected
- `REJECT`: `1` rejected

### 3.1 Self-target SEND

At tick 0, `EXP000_FOUNDER_A` selected `SEND` with `target_agent_id=EXP000_FOUNDER_A`. The Gateway bound the typed intent, and `LawValidator` correctly rejected the self-target. No message was committed.

### 3.2 Unknown proposal identifiers

All six selected `ACCEPT` actions and the one selected `REJECT` action emitted a proposal identifier that did not match any canonical proposal ID in the reconstructed pending-proposal state. Observed noncanonical values included:

- `exp000_proposal`
- `EXP000_FOUNDER_A`
- `exp000_founder_proposal`
- `proposal_id`

No malformed JSON or payload-shape failure occurred; these were syntactically valid but referentially invalid payloads.

## 4. Action-compatible referent split

The seven unknown-proposal-ID cases divide into two mechanistically distinct groups when checked against the pending proposals visible at the same tick boundary.

### A. A compatible incoming proposal existed: 3 cases

- tick 2, actor `EXP000_FOUNDER_A`, selected `ACCEPT`
- tick 8, actor `EXP000_FOUNDER_A`, selected `ACCEPT`
- tick 14, actor `EXP000_FOUNDER_C`, selected `REJECT`

In these cases at least one pending proposal targeted the acting agent, so a law-admissible canonical proposal reference existed in the world state. The emitted payload nevertheless used a noncanonical identifier. These are the strongest direct evidence for a protocol-reference grounding failure.

### B. No compatible incoming proposal existed: 4 cases

- tick 9, actor `EXP000_FOUNDER_B`, selected `ACCEPT`
- tick 12, actor `EXP000_FOUNDER_B`, selected `ACCEPT`
- tick 14, actor `EXP000_FOUNDER_B`, selected `ACCEPT`
- tick 15, actor `EXP000_FOUNDER_B`, selected `ACCEPT`

The reconstructed pending proposal set contained no proposal targeting `EXP000_FOUNDER_B` at these boundaries. Therefore even perfect copying of an existing proposal ID could not have made these four selected `ACCEPT` actions law-admissible. These cases reflect action-availability mismatch under the deliberately unmasked score selector, not reference grounding alone.

## 5. Bounded conclusion

The live pilot exposed **two separate protocol-level issues**, not one:

1. **Reference grounding:** when a compatible proposal existed, the payload generator could still emit a generic or invented identifier instead of the exact canonical proposal reference (`3` directly action-compatible cases).
2. **Action availability:** the preregistered selector can select `ACCEPT` when no incoming proposal is available (`4` cases), because V1 intentionally applies no legality/action-availability mask.

The remaining law rejection was one self-target SEND.

Therefore it would be incorrect to attribute all eight law rejections, or all zero births, solely to opaque proposal-ID copying. The reference-grounding defect is real and directly observed, but a future run can still contain mechanically unavailable selected actions unless action availability is separately changed in a preregistered intervention.

## 6. Existing implementation leverage

The repository already contains researcher-only I-05R4 reference-grounding primitives in `src/alifelm/model/motor_diagnostics.py`:

- `GroundingHandleMap`
- `render_with_local_handles`
- `forced_grounding_schema`
- `map_handle_candidate`

These primitives alias visible peer/proposal identifiers to context-local handles such as `P0` and `R0`, then map a model-selected handle back to the unchanged canonical identifier before domain validation. They are diagnostic/research-side code today and are **not yet admitted as the LIVE runtime contract**.

This existing path is the preferred starting point for the next bounded intervention; a new ad-hoc grounding system should not be invented unless the existing treatment is shown insufficient.

## 7. Next boundary

Before any new model forward:

1. verify from stored cognition evidence that the exact compatible proposal references were actually present in the model-visible rendered inputs for the three action-compatible failures;
2. freeze a separate reference-grounding intervention using context-local handles without changing the C10 action score selector;
3. explicitly distinguish reference-domain constraints from action-availability masking;
4. keep any action-availability intervention separate unless it is independently preregistered.
