# WORLD EXP-000 Live Grounding Pilot Result V1

Status: **LIVE_GROUNDING_PILOT_COMPLETE / VM SEALED / OFF-MACHINE HASH VERIFIED**

## 1. Scope

This record freezes the result of the preregistered `WORLD_EXP000_LIVE_GROUNDING_PILOT_V1` continuous multi-agent run. The run used the previously admitted deterministic C10 score selector and added only the preregistered proposal-handle payload grounding treatment for already-selected ACCEPT/REJECT actions. Action availability masking, law-eligibility filtering, retries, fallbacks, repairs, agent-ID aliasing, resources, geography, game mechanics, and neural heredity remained disabled.

This record establishes an engineering/scientific trajectory result, not a claim of social intelligence, evolutionary adaptation, culture, or civilization.

## 2. Execution identity

- preregistration commit: `76e666e5a51a93ea2c46bf10bda2ccf8c6f17b35`
- execution commit: `3b1580d972a1c85d83b64be3500197d397b4c458`
- run ID: `WORLD_EXP000_LIVE_GROUNDING_PILOT_V1_R1`
- founders: `EXP000_FOUNDER_A`, `EXP000_FOUNDER_B`, `EXP000_FOUNDER_C`
- horizon: `20` ticks
- lifespan: `20` ticks
- maturity delay: `0`
- refractory interval: `0`
- population capacity: `6`
- context policy: `exp000-context` v1.0.0 with max prior visible records `2`
- score selector: frozen C10 FA-prefill -> BASE scoring, `T=1.0`, deterministic opportunity-hash categorical selection
- proposal grounding: local `R0..Rn` proposal handles for ACCEPT/REJECT payload generation only
- proposal-handle domain: all visible proposal references, not law-eligible-only references
- action-availability mask: disabled
- agent-ID aliasing: disabled

## 3. Primary integrity result

Two manifests were produced by the runner.

### Base live manifest

- status: `LIVE_PILOT_COMPLETE`
- result digest: `9b8d4f63a3ae3311e6a3893928f3a971b3cfb6af20c80413f66cfbe0953af4d7`
- gates: `G0=true`, `G1=true`, `G2=true`, `G3=true`

### Grounding-specific manifest

- status: `LIVE_GROUNDING_PILOT_COMPLETE`
- result digest: `e8dca7b47bb4239ec3210a6f0fbbb7a9bfe376a440634f3307e05fa9b95966b5`
- gates:
  - `G0=true`
  - `G1_cognition_integrity=true`
  - `G2_proposal_handle_integrity=true`
  - `G3_canonical_commit_integrity=true`
  - `G4_persistence_replay_integrity=true`

Proposal-handle integrity summary:

- treated attempts: `4`
- baseline/no-visible-reference attempts: `1`
- invalid grounding records: `0`
- missing grounding records: `0`

SQLite read-only `PRAGMA integrity_check` returned `ok`.

## 4. Observed trajectory

The run completed at tick `20` with final status `COMPLETED`.

Selected action distribution:

- `WAIT`: `35`
- `SEND`: `16`
- `PROPOSE`: `8`
- `ACCEPT`: `5`
- `REJECT`: `0`

Canonical trajectory outputs:

- committed messages: `9`
- reproduction proposals created: `8`
- successful births: `2`
- birth conflicts: `0`
- natural deaths: `3`
- maximum generation depth: `1`
- final population: `2`

The founders naturally died under the frozen lifespan boundary. Two Generation-1 children remained at the final boundary.

## 5. Birth evidence

### Birth 1

- birth tick: `15`
- first active tick: `16`
- child ID: `dc9506bb1d703f455def753c4a92793a98befa01114871216c901eacf7204544`
- parents: `EXP000_FOUNDER_C`, `EXP000_FOUNDER_B`
- proposal ID: `f0fe073f72bbe4637896bea3296f535697bc48a45e924fa41b06123852628232`

The child subsequently received cognition opportunities and produced the following selected-action sequence before the bounded run ended:

- tick 16: `SEND` (law rejected)
- tick 17: `PROPOSE` (law admitted)
- tick 18: `PROPOSE` (law admitted)
- tick 19: `WAIT` (law admitted)

Therefore the first child was not merely instantiated in state; it entered the next-tick cognition lifecycle and generated further canonical interaction attempts.

### Birth 2

- birth tick: `19`
- first active tick: `20`
- child ID: `11ebd37d5eabb4e00a61e6e07045aba6a3bb0cd8774f2b220f5826c06441b07f`
- parents: `EXP000_FOUNDER_B`, `EXP000_FOUNDER_C`
- proposal ID: `a8b38b964de0da6dbc197174854e927a3bb263d373010003207a58315eec0c4b`

No cognition action was recorded for the second child before the horizon boundary, which is expected from the frozen `first_active_tick=20` / horizon `20` configuration.

## 6. Interpretation

This run closes the previously unverified minimal EXP-000 lifecycle path:

`real-model cognition -> PROPOSE -> visible proposal -> ACCEPT -> proposal-handle resolution -> CognitionGateway -> LawValidator -> canonical BirthTransition -> child activation -> child cognition`.

The path occurred without an action-availability mask, without filtering handles to law-eligible proposals, without retry/fallback/repair, without a social reward, and without a post-hoc minimum-birth success threshold.

The run therefore supports the bounded engineering claim that the current EXP-000 engine can sustain a continuous durable multi-agent trajectory in which real-model agents communicate, create bilateral reproduction proposals, accept proposals, produce canonical children, die naturally, and leave a next generation that can itself enter cognition.

It does **not** establish stable population dynamics, calibrated reproductive competence, beneficial social behavior, evolutionary adaptation, neural heredity, resource-based selection, culture, or civilization.

## 7. Preservation

The sealed recovery directory contains `195` files and all files passed internal SHA-256 verification. The canonical archive passed both gzip and tar verification. The Windows off-machine copies were then verified byte-for-byte against the frozen VM hashes.

Frozen identities:

- base `manifest.json`: `aa70c88392f52a018af2ea87f096360e0bfd362cb795668e0216215e57490320`
- `grounding_manifest.json`: `1cb4f18c2a4239f73d00c8065353a7f835b5d32abc446e29b70b24d3ecb4e281`
- stdout log: `d8d4826f0a6edde10ea7f291f9b97053b27c54e6628605d72376d5f365e6a37b`
- seal `SHA256SUMS`: `364249a960db2ef3a354c46e8e3e505876e61b99185cc9058f9f6826e3ac6a14`
- canonical archive: `dc7f904957a90be998df603b78c993b5ebdb55ccdd4d0aa20949dca80a9df227`

Canonical VM archive path:

`/workspace/WORLD_EXP000_LIVE_GROUNDING_PILOT_V1_3B1580D_R1_CANONICAL.tar.gz`

Off-machine destination:

`E:\WORLD\RECOVERY\EXP000_LIVE_GROUNDING_PILOT_V1_R1_20260906`

The Windows destination hashes for the canonical archive, base manifest, grounding manifest, stdout, and `SHA256SUMS` exactly matched the frozen VM identities above.

## 8. Milestone decision

EXP-000 has reached the minimum artificial-life engine milestone for the present project scope and is formally closed for this engineering stage.

The next engineering milestone should move to a read-only researcher Observatory UI and longer durability/soak observation before adding new causal variables such as heredity, resources, geography, survival pressure, group structure, or game mechanics.
