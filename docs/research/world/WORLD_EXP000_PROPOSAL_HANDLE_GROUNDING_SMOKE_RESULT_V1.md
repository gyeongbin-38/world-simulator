# WORLD EXP-000 Proposal Handle Grounding Smoke Result V1

Status: **GROUNDING_SMOKE_PASS / VM SEALED / OFF-MACHINE BACKUP PENDING**

## 1. Scope

This record freezes the result of the preregistered `WORLD_EXP000_PROPOSAL_HANDLE_GROUNDING_SMOKE_V1` payload-only source-trajectory smoke. The smoke reconstructed three exact source contexts from the sealed LIVE EXP-000 R1 trajectory and reran only the already-selected ACCEPT/REJECT payload stage with context-local proposal handles. It did not rerun the action selector and did not commit simulation state.

## 2. Execution identity

- grounding pilot preregistration commit: `8f77bbefd70bcdb54c7fb8d36542166375057281`
- grounding smoke execution commit: `58bb49262efa61cef6c32b2db90258e12c765e77`
- source LIVE pilot result digest: `b82267d7769cbc4dc56aaa3c5f82e5e66b1b669ef407b4c58d1a994b4ae29f00`
- source LIVE pilot canonical archive SHA-256: `b9d6e31df6e01e1ddabd943b40601255c7d80361b3eb5b3c217f25f5cc5b36e3`
- source LIVE pilot manifest SHA-256: `8c239e0c3550ec435ccd8ef2a718845a88d623d43cdcb7151d0b11825768e4e2`
- source seal SHA256SUMS SHA-256: `6abbbc19b44cbd0111927e5052098795f5e83ee74de9acca506a315457dbbbfa`
- canonical runtime pip-freeze SHA-256: `a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf`

## 3. Primary result

The smoke completed with:

- status: `GROUNDING_SMOKE_PASS`
- result digest: `bbbca1f5c278ea21fcc4ec203e3ceacbe4a1087806f89dfb629105214d74f5d5`
- gates: `G0=true`, `G1_source_context_identity=true`, `G2_handle_mapping=true`, `G3_phase_integrity=true`, `G4_snapshot_unchanged=true`
- action selector rerun: `false`
- simulation-state commits: `0`
- model weight updates: `0`
- retries/fallbacks/repairs: `0`
- descriptive LawValidator admissions: `2 / 3`

## 4. VM preservation

The grounding-smoke evidence was sealed after execution. The sealed directory contains `20` files and every file passed internal SHA-256 verification. The canonical archive passed both gzip and tar verification.

Frozen VM identities:

- manifest SHA-256: `aedfa2f58c9b127ff9c04e5d79bebe7c7b9e892c831fa5ffac385abcff505260`
- stdout SHA-256: `920061e3d342e27f6aafc1abb7fa7fda3a538b50b14830d0442ab0e4e355a2d9`
- seal `SHA256SUMS` SHA-256: `31ff48bfe03e256e95f70c6c82a1028b51f3f5f5c0e19af11854555d44b35675`
- canonical archive SHA-256: `ca3ae00fb89dfbb628254410189328381ae0901b8bb7d502f93fe6026e918dd3`

Canonical VM archive path:

`/workspace/WORLD_EXP000_PROPOSAL_HANDLE_GROUNDING_SMOKE_V1_58BB492_R1_CANONICAL.tar.gz`

Off-machine verification is not yet claimed in this record.

## 5. Case results

### Tick 2 / EXP000_FOUNDER_A / ACCEPT

- raw local handle selected: `R0`
- mapped canonical proposal ID: `ecb428778240a75dc937feb2a0ba8e61639721ef5fd562924cb7a33b34bc1543`
- Gateway intent kind: `ACCEPT`
- LawValidator admitted: `false`

This is a successful reference-grounding event but a semantic/eligibility miss. `R0` mapped to a visible proposal that was not a law-admissible incoming pending proposal for the actor. This confirms that the intervention is a visible-reference grounding layer rather than a legality mask.

### Tick 8 / EXP000_FOUNDER_A / ACCEPT

- raw local handle selected: `R0`
- mapped canonical proposal ID: `25c056c7f6681eb948a0958129a12453a88c5a6900da3e18b8eedd67adfd4954`
- Gateway intent kind: `ACCEPT`
- LawValidator admitted: `true`

The source baseline had generated the invented identifier `exp000_proposal`. With local handles, the payload resolved to an exact canonical visible proposal and the unchanged LawValidator admitted the ACCEPT intent.

### Tick 14 / EXP000_FOUNDER_C / REJECT

- raw local handle selected: `R0`
- mapped canonical proposal ID: `af28da031ea39fa90514e94ad5ba8a0e08571b2c5c662fbaa78a803a657e2cdf`
- Gateway intent kind: `REJECT`
- LawValidator admitted: `true`

The source baseline had generated the generic identifier `proposal_id`. With local handles, the payload resolved to an exact canonical visible proposal and the unchanged LawValidator admitted the REJECT intent.

## 6. Interpretation

The smoke establishes that the long opaque proposal-ID generation failure can be removed by a context-local handle interface while preserving canonical world authority, frozen C10 phase identity, Gateway identity binding, LawValidator authority, and no-retry/no-fallback semantics.

The result does **not** establish that the model always chooses the semantically or legally correct proposal. Tick 2 demonstrates the remaining distinction: reference grounding succeeded, but the model selected a visible proposal that was not admissible for that actor.

Therefore the current remaining failure modes are now separated as:

1. **reference grounding** — materially mitigated by the handle intervention;
2. **semantic proposal selection / action availability** — still observable and intentionally not masked;
3. **agent target grounding** — unchanged in V1 and still responsible for the prior self-SEND failure.

## 7. Next milestone

Before any follow-up continuous LIVE run:

1. copy the canonical grounding-smoke archive and key evidence off-machine and verify destination hashes;
2. preregister a new versioned LIVE EXP-000 run using the same score selector plus proposal-handle payload grounding, with no action-availability mask;
3. treat births and LawValidator admissions as descriptive trajectory outcomes rather than required thresholds.
