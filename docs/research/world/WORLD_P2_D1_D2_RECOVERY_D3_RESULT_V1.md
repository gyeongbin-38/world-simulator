# WORLD P2 D1/D2 Recovery + D3 First Complete Result V1

Status: **RECORDED RECOVERY / RESULT LINEAGE**

## 1. Scope

This document records the 2026-09-06 recovery state for P2-D1 and P2-D2 and the first integrity-passing complete P2-D3 measurement. It is a preservation and scientific-lineage record; it does not retroactively replace historical canonical archive identities.

Two identities are kept separate throughout:

- **historical canonical identity**: hashes and result digests recorded by the original run lineage;
- **recovery identity**: hashes of newly reproduced or newly completed evidence preserved after the historical raw artifacts became unavailable.

A historical raw artifact is not described as recovered unless its original bytes are actually present and hash-verified.

## 2. P2-D1 recovery

Study: `WORLD_P2_D1_DECISION_BOUNDARY_LOCALIZATION_V1`

Historical lineage:

- scientific implementation commit: `5f7f5e02a66c253e0352771cbb35f0db6c408072`
- historical result-record commit: `e3f7f76219724641056acf095f384f80291c8bde`
- historical result digest: `865616cdb65e5f4c969a9302c02bb285167db06a905e1497b05e4e0912935c20`
- historical details SHA-256: `0e5e62709d58168c9922645c1d05d54a7f5c417b68b3f461b4558d3706ca3b17`
- historical canonical archive SHA-256: `c42999e001c789a4a43fa14962119315066b2df6c66e3b472ce76a6f27cad2f1`

Recovery run:

- status: `P2_D1_MEASUREMENT_COMPLETE`
- localization: `RANK_CONTEXT_SENSITIVE`
- integrity: pass
- recovery details SHA-256: `0e5e62709d58168c9922645c1d05d54a7f5c417b68b3f461b4558d3706ca3b17`
- recovery summary SHA-256: `2355558f1424cacae0ba8819621c6eef532e48b59bbeeb9ab314ccdd829e1e40`
- recovery stdout SHA-256: `bbeabf9305ce2d912b33026a1b18e7f9fc629762f075b946a0e2f1031827afbe`
- sealed recovery archive SHA-256: `7c56da7213e270fe60d2d8fe67d6aabe005dc9ff5bed79bb91120244a7743e80`

The recovered `details.json` is byte-for-byte identical to the historical scientific payload. The recovery summary/result digest are execution-environment-sensitive and are not asserted to be historical-byte-identical.

Recovery state:

- scientific payload: **EXACT_REPRODUCED**
- sealed recovery archive: **PRESERVED_AND_OFF_MACHINE_HASH_VERIFIED**
- historical canonical archive bytes: **NOT_YET_FOUND**

## 3. P2-D2 recovery

Study: `WORLD_P2_D2_KV_CACHE_CAUSAL_LOCALIZATION_V1`

Historical lineage:

- historical scientific HEAD: `9cfa129c260173790865825f6d6283b57bac555c`
- historical result digest: `cf03450cdcde79e0f2fe78b4caf7bda6df99bec159246a15817194dcc61b9a61`
- historical details SHA-256: `e554f6a113597cd8d3f1d9c923f7ee4e17c59c51e9933cd398a2118f15731608`
- historical summary SHA-256: `69a9333c8c3e1217655973ac3246846bc2780ea7b9f6135972a58f232f5327b4`
- historical stdout SHA-256: `f23fd36a57394e7b15784d05b5bf6b53ab744994f48c09c2f890abff8f0e5522`
- historical canonical archive SHA-256: `f811de72d5faf1e9d56de534f73c8ecac101d5e22f12256ea00c14be6b101559`

Recovery run:

- status: `P2_D2_MEASUREMENT_COMPLETE`
- integrity: pass
- localization: `UNION_BIDIRECTIONAL_NONUNIVERSAL`
- selected blocks: `Q2`, `Q1`
- selected layers: `[9, 10]`
- recovery details SHA-256: `e554f6a113597cd8d3f1d9c923f7ee4e17c59c51e9933cd398a2118f15731608`
- recovery summary SHA-256: `37dcddf79b5cc7f197d220d11bb1b0d80bfc87d65dd77c618ec5acc3a89117fb`
- recovery stdout SHA-256: `1a4d8844341751240466089424d46a5e38e54c466186bafc164b3be294cc708c`
- sealed recovery archive SHA-256: `ae48541bc474771b676717b5b2a156d6e0b9553867b25111b41f6a64e3fbfc3b`

The recovered `details.json` is byte-for-byte identical to the historical D2 scientific payload.

Recovery state:

- scientific payload: **EXACT_REPRODUCED**
- sealed recovery archive: **PRESERVED_AND_OFF_MACHINE_HASH_VERIFIED**
- historical canonical archive bytes: **NOT_YET_FOUND**

Bounded scientific result retained from D2: WORLD-prefill KV state at layers 9 and 10 has strong causal leverage over the D1 SEND/WAIT decision regime, but the nonuniversal induction result does not establish that these layers are the sole mediator.

## 4. P2-D3 execution lineage

Study: `WORLD_P2_D3_TARGETED_ADAPTER_SCALING_V1`

Frozen lineage:

- preregistration commit: `8cbba8828fbb3f5b6bb496f2476c78b420036296`
- final R2-compatible scientific HEAD used by recovery R3: `ee0b1da2bbda35c026f9ca38aa7dcea92f815ce0`
- target layers: `[9, 10]`
- scale candidates: `[0.0, 0.25, 0.5, 0.75, 1.0]`

Execution history:

- R1 reached real inference but failed on a protocol-neutral serializer incompatibility.
- R2 fixed only the serializer/runtime bootstrap and was later interrupted before completion; it is not a scientific result.
- Recovery R3 reused the frozen D3 scientific intervention and R2 serializer fix, replaced only source-artifact verification with recovery-aware exact-hash gates, and completed the preregistered measurement.

## 5. P2-D3 first complete result

Recovery R3 result:

- status: `P2_D3_MEASUREMENT_COMPLETE`
- integrity: `true`
- selected scale: `0.0`
- repair proxy: `SCORE_PROXY_NOT_REPAIRED`
- result digest: `f47c082fc03d0129b82ccf404f30e39b8fed76e77650a303074d4258b90fa130`
- details SHA-256: `8646a7d897278f639d80295766649b4ab4506e809d6b3122994339fa7b3a5f1b`
- summary SHA-256: `74c92110510b6d477cd97de67f3fb99879331c2529ce22949aaeb44d740152fa`
- stdout SHA-256: `c2f0aba8b0bd0ac2cc884db99119ee7950791175eb6ea0053243ea761dd16b88`
- sealed result archive SHA-256: `9c2090ff25dce3ae6431fe78abecb774b8ac365880c50d521b270b3766e73f54`

Integrity checks all passed:

- exact repeat serialization equality: `true`
- LoRA scaling metadata restored: `true`
- D1 source unchanged: `true`
- D2 source unchanged: `true`
- weight updates: `0`
- simulation-state commits: `0`

The sealed D3 archive was copied off-machine and its SHA-256 was independently verified after transfer.

## 6. Combined scientific interpretation

The bounded D1 -> D2 -> D3 chain is:

1. D1: FA WORLD-prefill moves the fixed BASE selector from a universal SEND-dominant regime to a universal WAIT-dominant regime while context-sensitive lower-order score structure remains.
2. D2: directly transplanting WORLD-prefill KV state localizes strong causal leverage to layers 9 and 10.
3. D3: scaling all active LoRA contributions in layers 9 and 10, including selecting scale `0.0`, does not satisfy the preregistered score-repair proxy.

Therefore the strongest supported statement is:

> Layers 9 and 10 are an important causal locus for the D1 regime shift, but the scalar amplitude of LoRA contribution in those layers is not by itself a sufficient repair mechanism.

This does not yet distinguish whether the relevant mechanism is concentrated in key state, value state, both jointly, distributed cross-layer interactions, or another representation that is expressed through the retained KV cache.

## 7. Preservation rule for subsequent studies

No subsequent P2 diagnostic should advance until the immediately preceding complete result has all of the following:

1. immutable evidence root and stdout;
2. SHA-256 manifest;
3. sealed archive with gzip/tar verification;
4. off-machine copy;
5. independent destination SHA-256 verification.

Failed or interrupted attempts remain immutable evidence and are never overwritten or silently promoted to canonical scientific results.
