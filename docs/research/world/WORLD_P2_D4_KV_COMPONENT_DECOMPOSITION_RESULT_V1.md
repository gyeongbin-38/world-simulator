# WORLD P2-D4 — KV Component Decomposition Result V1

Status: **P2_D4_MEASUREMENT_COMPLETE / INTEGRITY PASS**

## 1. Identity

- Study: `WORLD_P2_D4_KV_COMPONENT_DECOMPOSITION_V1`
- Preregistration commit: `80e449ee464c8c682ae33f2cd026e88ea6fa351c`
- Scientific execution commit: `ba71f0e8686390c91fe921d197ab180973428e68`
- Source P2 interpretation remains: `C10_NOT_BEHAVIORALLY_ADMITTED`
- No simulation-state commits occurred.
- No model weight updates occurred.

## 2. Preservation identity

- result digest: `e7a7bfae9ecaaebf862727ed31b228be921ea6a4ac889520b6361279c3ad76d6`
- details SHA-256: `16c89537fcf2c211ad9e64112a0a455d0da9e7c07235fb563b488dba7bcea0bc`
- summary SHA-256: `7203e8406fe939fddc110987a51ac7413813f2088681f29b875754983642b1c9`
- preservation manifest SHA-256: `4725744275aa103a8077c8f183833c82d24662a2dc60401df0cc7911816b235e`
- canonical archive SHA-256: `4ef7b31a9339f3e1cf3d26ba47bc942b706c5812cdff8286f6d4cacea5e004ac`
- canonical archive verification: `P2_D4_R1_CANONICAL_ARCHIVE_VERIFIED`
- gzip integrity: pass
- off-machine Windows E: copy: hash-verified for archive, details, summary, and preservation manifest

## 3. Stage-A component screening

Frozen candidates were evaluated on the 20-context screening cohort in rescue and induction directions.

Median symmetric mediator scores:

| Candidate | Median symmetric mediator score |
|---|---:|
| `L9_V` | `0.7531347962382444` |
| `L9_L10_V` | `0.5501567398119123` |
| `L9_L10_K` | `0.5267221663610733` |
| `L10_K` | `0.4537240055600523` |
| `L9_K` | `0.148105064874819` |
| `L10_V` | `-0.03870292887029288` |

The preregistered selection rule therefore advanced:

> `L9_V`

This is transformer layer 9 value-cache state only.

## 4. Stage-B full-cohort confirmation

Selected candidate: `L9_V`

Across all 160 frozen contexts:

- median symmetric mediator score: `0.7402240896358543`
- rescue sign flips: `62 / 160`
- induction sign flips: `96 / 160`
- rescue total-rank-1 distribution: `SEND 62`, `WAIT 98`
- induction total-rank-1 distribution: `SEND 64`, `WAIT 96`
- rescue WAIT-minus-SEND gap median: `0.0`
- induction WAIT-minus-SEND gap median: `0.5`

The exact repeat of the selected full-cohort rescue/induction conditions completed `160 / 160` and was serialization-identical.

## 5. Integrity

All integrity conditions passed:

- Stage-0 positive controls: pass
- exact repeat serialized equality: true
- source D1 unchanged: true
- source D2 unchanged: true
- source D3 unchanged: true
- retries: `0`
- repairs: `0`
- fallbacks: `0`
- simulation-state commits: `0`
- weight updates: `0`

## 6. Bounded scientific interpretation

P2-D1 established the FA WORLD-prefill SEND -> WAIT decision-regime shift while holding the selector BASE.

P2-D2 localized strong causal leverage to WORLD-prefill KV state at transformer layers 9 and 10.

P2-D3 showed that scalar LoRA scaling at layers 9 and 10, including scale `0.0`, did not satisfy the preregistered score-repair proxy.

P2-D4 further decomposes the D2 KV locus and establishes the bounded result:

> Among the preregistered layer-9/layer-10 K/V component candidates, layer 9 value-cache state (`L9_V`) is the strongest single-component mediator candidate for the frozen D1 SEND/WAIT regime shift.

The result does **not** establish that `L9_V` is the unique or sole cause. Rescue is nonuniversal (`62/160` sign flips), induction is nonuniversal (`96/160` sign flips), and the screening ordering is non-additive: `L9_V` exceeds `L9_L10_V`, while `L10_V` alone is negative. These observations are compatible with distributed and interaction-dependent mediation across K/V state and layers.

The mediator score is a normalized causal-axis diagnostic defined by the preregistered D2/D4 protocol. It is not variance explained and must not be described as "74% of the phenomenon explained."

## 7. Project decision

P2-D4 supplies sufficient mechanistic evidence for the current engineering objective: validate that WORLD-prefill internal state causally reaches the fixed selector and localize a strong mediator candidate.

Further head-, token-, residual-, or feature-level interpretation requires a separately preregistered mechanistic follow-up and is not a blocker for the next platform milestone.

The recommended next milestone is **LIVE EXP-000 integration**: run multiple real-model agents through the existing deterministic simulation kernel so that communication, reproduction, birth, death, lineage, persistence/replay, and researcher observation occur in one continuous experiment.