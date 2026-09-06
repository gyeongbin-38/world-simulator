# WORLD EXP-000 Proposal Reference Visibility Audit V1

Status: **READ-ONLY AUDIT COMPLETE / NO NEW MODEL FORWARD**

## 1. Scope

This audit classifies the post-run grounding failures observed in `WORLD_EXP000_LIVE_PILOT_V1_R1` without changing any model, selector, world law, durable state, or evidence bytes. It uses only the sealed 20 tick records and CAS evidence from the completed pilot.

Source pilot identity:

- execution commit: `55b4c5128a40c2e68a6a7cc205424e7e6a802314`
- result digest: `b82267d7769cbc4dc56aaa3c5f82e5e66b1b669ef407b4c58d1a994b4ae29f00`
- canonical archive SHA-256: `b9d6e31df6e01e1ddabd943b40601255c7d80361b3eb5b3c217f25f5cc5b36e3`
- off-machine hash verification: PASS

## 2. Law rejection classification

The completed pilot contained exactly 8 LawValidator rejections, matching the manifest count:

- `SEND / SELF_TARGET`: 1
- `ACCEPT / UNKNOWN_PROPOSAL_ID`: 6
- `REJECT / UNKNOWN_PROPOSAL_ID`: 1

Thus all 8 law rejections are accounted for by two concrete mechanisms: one self-targeting SEND and seven invalid proposal references.

## 3. Proposal-reference visibility audit

Three of the seven ACCEPT/REJECT failures occurred when the acting agent had one or more compatible visible incoming pending proposals. The exact canonical proposal identifiers were present verbatim in the model-facing rendered input.

### Tick 2 — `EXP000_FOUNDER_A` — ACCEPT

Generated proposal ID:

`exp000_proposal`

One compatible incoming pending proposal existed and was visible verbatim:

`d86778565f4b91227760ffd1524385480888de8c906807dfababdd2ef6e1d06a`

Result: generated reference was not a canonical proposal ID despite the exact valid reference being visible.

### Tick 8 — `EXP000_FOUNDER_A` — ACCEPT

Generated proposal ID:

`exp000_proposal`

Two compatible incoming pending proposals existed and both were visible verbatim:

- `d86778565f4b91227760ffd1524385480888de8c906807dfababdd2ef6e1d06a`
- `25c056c7f6681eb948a0958129a12453a88c5a6900da3e18b8eedd67adfd4954`

Result: generated reference was not a canonical proposal ID despite valid references being visible.

### Tick 14 — `EXP000_FOUNDER_C` — REJECT

Generated proposal ID:

`proposal_id`

Four compatible incoming pending proposals existed and all were visible verbatim:

- `ecb428778240a75dc937feb2a0ba8e61639721ef5fd562924cb7a33b34bc1543`
- `f7efc22e68d5a68830aa78f817a5103476aedb6e4b23544f976b9b5a4c9aa719`
- `3d38d9addbccf131f85fa1dfc90d578cf6adb04629ef19b49d512b9de1b937f8`
- `af28da031ea39fa90514e94ad5ba8a0e08571b2c5c662fbaa78a803a657e2cdf`

The literal string `proposal_id` also appears in the action-contract text as `payload_fields=proposal_id`. Therefore a naive substring test reports `generated_id_visible=True`, but this is not evidence that the generated value matched any canonical proposal identifier. It was a field-name placeholder, not a protocol-object reference.

## 4. Availability separation

The other four ACCEPT failures occurred for actors that had no compatible incoming pending proposal at that opportunity. Those failures are not evidence of reference-copy failure alone. They expose a separate action-availability issue: the frozen selector can choose ACCEPT even when current law makes no ACCEPT target available.

This distinction is required for the next intervention:

- **reference grounding problem:** selected ACCEPT/REJECT, compatible proposal exists and is visible, but payload does not reference a canonical proposal;
- **action availability problem:** selected ACCEPT/REJECT when no compatible proposal exists.

The two mechanisms must not be repaired in the same first intervention.

## 5. Conclusion

The proposal-reference grounding hypothesis is confirmed for the three eligible audited opportunities. The model was shown the exact canonical opaque proposal IDs, yet generated generic or invented identifier strings instead.

The next bounded intervention should therefore isolate payload-side proposal-reference grounding while keeping all of the following frozen:

- C10 score geometry;
- score-selector action order and `T=1.0`;
- deterministic opportunity-hash categorical selection;
- no action rewrite;
- no retry, fallback, or resampling;
- existing CognitionGateway and LawValidator authority;
- canonical proposal identities and world laws.

Action-availability handling remains a separate future study.