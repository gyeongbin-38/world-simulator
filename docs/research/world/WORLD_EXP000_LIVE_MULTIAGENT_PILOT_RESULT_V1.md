# WORLD EXP-000 Live Multi-Agent Pilot Result V1

Status: **LIVE_PILOT_COMPLETE / VM SEALED / OFF-MACHINE BACKUP PENDING**

## 1. Scope

This record freezes the observed result of the preregistered `WORLD_EXP000_LIVE_MULTIAGENT_PILOT_V1` bounded continuous multi-agent run. It is an engineering/scientific trajectory record, not an admission claim for social intelligence, reproductive competence, evolution, culture, or civilization.

## 2. Execution identity

- preregistration commit: `0aa0fdbeb4f9c0a04a52bdff54d0d751febacb1c`
- execution commit: `55b4c5128a40c2e68a6a7cc205424e7e6a802314`
- run ID: `WORLD_EXP000_LIVE_PILOT_V1_R1`
- founders: `EXP000_FOUNDER_A`, `EXP000_FOUNDER_B`, `EXP000_FOUNDER_C`
- horizon: `20` ticks
- lifespan: `20` ticks
- population capacity: `6`
- score selector: frozen C10 FA-prefill -> BASE branch scoring, `T=1.0`, deterministic opportunity-hash categorical selection
- retries/fallbacks/repairs/legality mask: disabled

## 3. Primary integrity result

The run completed with:

- status: `LIVE_PILOT_COMPLETE`
- result digest: `b82267d7769cbc4dc56aaa3c5f82e5e66b1b669ef407b4c58d1a994b4ae29f00`
- final tick: `20`
- final run status: `COMPLETED`
- gates: `G0=true`, `G1=true`, `G2=true`, `G3=true`
- SQLite read-only `PRAGMA integrity_check`: `ok`
- durable final boundary/replay integrity: PASS
- replay new cognition delta: `0`
- model weight updates: `0`

## 4. Observed trajectory

Across exactly 60 cognition opportunities (3 founders x 20 ticks):

- `WAIT`: 26
- `SEND`: 17
- `PROPOSE`: 10
- `ACCEPT`: 6
- `REJECT`: 1

Canonical trajectory outputs:

- committed messages: `16`
- reproduction proposals created: `10`
- successful births: `0`
- natural deaths: `3`
- parse/payload rejections: `0`
- law rejections: `8`
- maximum generation depth: `0`
- final population: `0`

The final population of zero is expected under the frozen lifespan boundary because all three founders naturally died at the horizon and no birth succeeded before then.

## 5. Bounded behavioral interpretation

The prior hard-argmax WAIT collapse did not recur under the preregistered score-selector architecture: non-WAIT actions were selected and multiple SEND/PROPOSE intents were successfully grounded, validated, and committed into canonical state.

However, successful reproduction did not occur. At least one directly inspected ACCEPT selected a non-existent opaque proposal identifier (`exp000_proposal`) rather than a visible canonical proposal ID and was rejected by `LawValidator`. The full set of eight law rejections requires a separate read-only post-run classification before the protocol-object grounding hypothesis can be stated as the dominant failure mode.

No post-hoc action-frequency or birth threshold is applied to this run. Zero births is an observed trajectory result, not an infrastructure failure.

## 6. VM preservation

The sealed recovery directory contains 202 files and passed internal SHA-256 verification. The canonical archive passed both gzip and tar verification.

Frozen VM identities:

- `manifest.json`: `8c239e0c3550ec435ccd8ef2a718845a88d623d43cdcb7151d0b11825768e4e2`
- stdout log: `4ebb2e40f59e2520f008ec4070d892a7ca10b25983b0948abc5be7958ba66215`
- launch log: `025de5b35f9ba2ace70eff42fa3b5c18c67d1b5e6639ef007ab9ab1010ec24ce`
- seal `SHA256SUMS`: `6abbbc19b44cbd0111927e5052098795f5e83ee74de9acca506a315457dbbbfa`
- canonical archive: `b9d6e31df6e01e1ddabd943b40601255c7d80361b3eb5b3c217f25f5cc5b36e3`

Canonical VM archive path:

`/workspace/WORLD_EXP000_LIVE_PILOT_V1_55B4C51_R1_CANONICAL.tar.gz`

Off-machine hash verification is intentionally not claimed in this record until the Windows destination hashes are checked.

## 7. Next analysis boundary

Before any corrected or follow-up live run:

1. copy the canonical archive and key evidence files off-machine and verify exact destination SHA-256 values;
2. perform a read-only classification of all 60 cognition opportunities, especially all eight law rejections;
3. determine whether ACCEPT/REJECT failures are dominated by opaque proposal-ID grounding, self-targeting, wrong-target selection, or another protocol-level failure;
4. preregister any grounding-layer intervention separately before new model forwards.
