# WORLD P2-D1 Pre-Inference Audit V1

Status: STATIC IMPLEMENTATION AUDIT COMPLETE; NO P2-D1 MODEL FORWARD HAS BEEN PERFORMED.

This audit reviews the implementation added after the frozen P2-D1 scientific preregistration at commit `44d8df09b452143ac8007a82d8d9ffd6f2593322`. It does not modify the P2-D1 scientific question, P2 source result, thresholds, action space, model input, or interpretation boundary.

## Frozen scientific source

- P2-D1 prereg/config commit: `44d8df09b452143ac8007a82d8d9ffd6f2593322`.
- P2 source interpretation remains `C10_NOT_BEHAVIORALLY_ADMITTED`.
- P2 source result digest remains `4226c5909fd13d8d769436d344a221d6f0c1746b08466ff6f5eb03303c0be563`.
- P2 canonical archive SHA-256 remains `61a19717cf089fb59b43e2b52efc31e28036449418e3aeba69c8dd0bbad17790`.
- Founder Freeze remains `NOT_ESTABLISHED`.

## Audit findings

1. The probe reuses the frozen P2 split cached topology: one WORLD-context prefill, one I3 suffix continuation, retained PKV, explicit adapter-state switch, and no WORLD-context recomputation after the switch.
2. The five action candidates remain the frozen `WAIT`, `SEND`, `PROPOSE`, `ACCEPT`, `REJECT` branches and canonical model labels from `ActionPresentation`.
3. Shared constrained tokens are advanced only while all five forced schemas expose identical canonical legal token-ID sets. Branch scores begin only at the first legal-set divergence.
4. Branch paths use deterministic constrained-greedy token selection and accumulate raw full-vocabulary token log-probability until the target action branch is logically unique. Alternate tokenizer paths are not marginalized; this was frozen in the pre-inference implementation note before observing D1 scores.
5. Both total and token-normalized mean branch scores, ranks, exact token IDs, token counts, common-prefix IDs, divergence step, phase counters, and repeat deltas are preserved.
6. C00 and C10 are the only D1 conditions. D1 cannot generate or commit an ActionIntent, update weights, retry, repair, fallback, calibrate scores, or relabel P2.
7. The runner verifies the restored P2 R3 summary/details/stdout against the canonical P2 archive and re-hashes source evidence before and after D1.
8. The hardened entrypoint additionally requires the live protocol/config bytes to be exactly equal to the files at the preregistration commit and requires current HEAD to descend from that preregistration commit.
9. No static blocker was identified that justifies changing the frozen scientific protocol before runtime validation.

## Residual runtime-only risks

The following cannot be closed without the canonical restored runtime and therefore remain runtime-validation items rather than protocol changes:

- real LM Format Enforcer legal-set behavior under the accepted tokenizer;
- whether all five forced schemas reach deterministic action-branch divergence inside the fail-closed guards;
- exact cached-attention behavior under the accepted OLMo-2 / PEFT / Transformers versions;
- BF16 exact-repeat equality on the target GPU;
- runtime cost and memory behavior of the 640 scored probes.

Any failure in these items before a complete D1 measurement is implementation/infrastructure evidence only. Failed output roots/stdout must remain immutable and a new versioned attempt must be used after a protocol-neutral fix.

## First-forward admission sequence

On a restored/new GPU Pod, do not execute D1 immediately. First restore the verified master backup, update the D1 implementation branch, run the dedicated P2-D1 tests together with the relevant phase/P2 regression tests, and run `tools/run_p2_d1.sh validate`. Only after those checks pass with the canonical runtime and unchanged source hashes is the first D1 model forward admissible.
