# WORLD EXP-000 Score-Selector A40 Smoke Result V1

Status: **INFRASTRUCTURE_PASS / OFF-MACHINE HASH VERIFIED**

## 1. Scope

This record freezes the observed result of the preregistered `WORLD_EXP000_SCORE_SELECTOR_A40_SMOKE_V1` deployment/integration smoke. The smoke was intentionally fixture-selected to exercise the non-WAIT conditional payload path and therefore is not a behavioral-frequency or social-competence result.

## 2. Execution identity

- smoke preregistration commit: `60c35d785ff9e15f05496ad9a12c7fa8f3885239`
- smoke execution commit: `769cf611cda535a8b590d5c826b90ca505deaac6`
- parent score-selector pilot preregistration commit: `0c10b121695a31000f9d1f675d7fb3c5378fc248`
- frozen D1 details SHA-256: `0e5e62709d58168c9922645c1d05d54a7f5c417b68b3f461b4558d3706ca3b17`
- base checkpoint SHA-256: `36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f`
- FA-v1 adapter SHA-256: `46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec`
- tokenizer aggregate SHA-256: `c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff`
- runtime pip-freeze SHA-256: `a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf`

## 3. Frozen fixture

- context class: `QUIET`
- case index: `4000`
- run ID: `i05r3-quiet-4000`
- tick: `2`
- actor: `A`
- opportunity ID: `cbf8914977ebb729ac940ee5cdcdecf23fc0680c99797cb2b1694b7c1b052daf`
- source-selected action: `SEND`
- selector seed digest: `91b37369db308547a211fd40ee5c6d01f5bf632bc125a30fd46bed3915f0e227`

## 4. Observed result

The smoke completed with:

- status: `INFRASTRUCTURE_PASS`
- result digest: `7e69dbc2c40509f0cc6f10906a5482cc4cc2d01a8a114e66cb836e72ff95a912`
- live C10 mean branch scores exactly matched the frozen D1 source row
- selected action: `SEND`
- payload parse status: `VALID`
- generated candidate: `DIRECT_TEXT`
- generated target: `B`
- generated body: `B is a 2-year-old agent.`
- Gateway-bound intent kind: `SEND`
- descriptive LawValidator admission: `true`
- C10 prefill adapter: `true` (FA-v1)
- C10 selector adapter: `false` (BASE)
- WORLD context recomputed after switch: `false`
- bound Snapshot unchanged: `true`
- simulation-state commits: `0`
- model weight updates: `0`
- retries: `0`
- fallbacks: `0`
- repairs: `0`

## 5. Preservation

VM preservation hashes:

- `manifest.json`: `49c2591124d7cc182b232a0d95243e44ee5a4dd3e29016a1faa79f7863c34d8b`
- stdout: `6ab7267fedc1770807cbde803e05a9a30d7217e227e054f4a974e23a3610143a`
- seal `SHA256SUMS`: `1217185130b7cdb4146895c86693acc500bf0cfe037cfb3b7d76c4ece6874fb4`
- canonical archive: `d60225464d8c89dea55fad82fc977895fb69bdd597ee6e0882e0ced2789817f2`

The canonical archive passed gzip and tar verification. The archive, manifest, stdout, and `SHA256SUMS` were copied to Windows `E:\WORLD\RECOVERY\EXP000_SCORE_SELECTOR_A40_SMOKE_20260906` and all four destination SHA-256 hashes exactly matched the VM values above.

## 6. Bounded interpretation

This result establishes that the accepted A40 runtime can reproduce the frozen D1 C10 score geometry for the preregistered fixture, make the deterministic V1 categorical selection, generate a payload for the already-selected action without re-selecting it, bind the resulting candidate through the existing CognitionGateway, and preserve the no-commit/no-update/no-retry boundaries.

It does **not** establish autonomous social competence, action-frequency calibration, reproductive competence, long-horizon stability, or emergent social behavior. The fixture was deliberately selected to exercise the SEND payload path.

## 7. Next milestone

Proceed to the separately preregistered bounded LIVE EXP-000 multi-agent pilot. The next study must use the same immutable score-selector rule and existing deterministic kernel/persistence authority, while measuring the resulting trajectory descriptively rather than imposing an activity target.
