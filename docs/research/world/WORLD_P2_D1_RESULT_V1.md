# WORLD P2-D1 Decision-Boundary Localization — Canonical Result

## Identity

- Study: `WORLD_P2_D1_DECISION_BOUNDARY_LOCALIZATION_V1`
- Scientific implementation commit: `5f7f5e02a66c253e0352771cbb35f0db6c408072`
- Preregistration commit: `44d8df09b452143ac8007a82d8d9ffd6f2593322`
- Frozen source P2 result: `C10_NOT_BEHAVIORALLY_ADMITTED`
- Frozen source P2 result digest: `4226c5909fd13d8d769436d344a221d6f0c1746b08466ff6f5eb03303c0be563`

## Execution provenance

### R1 — interrupted infrastructure attempt

The first model-forward attempt was interrupted after `C00 160/160` and during `C10` primary (`100/160` printed). It produced no `summary.json` and no `details.json`; it is not a scientific result.

Preserved R1 evidence:

- interrupted archive SHA-256: `5bfcdfbc031751e60db0db04217585962b5b792b536be7e8ff4b2866f9d08a0e`
- stdout SHA-256: `e12fbb2342a95db5f6d8ae388c9171693d851791e4c5f714460fefffacc69fe5`
- run-plan SHA-256: `c6e3f2c52639c479f3016528760663fb724f18b49a8201d8a9f08f64a53327f3`

### R2 — canonical successful run

- status: `P2_D1_MEASUREMENT_COMPLETE`
- integrity: `true`
- localization tag: `RANK_CONTEXT_SENSITIVE`
- result digest: `865616cdb65e5f4c969a9302c02bb285167db06a905e1497b05e4e0912935c20`
- details SHA-256: `0e5e62709d58168c9922645c1d05d54a7f5c417b68b3f461b4558d3706ca3b17`
- canonical archive SHA-256: `c42999e001c789a4a43fa14962119315066b2df6c66e3b472ce76a6f27cad2f1`
- source P2 unchanged: `true`
- retries: `0`
- repairs: `0`
- fallbacks: `0`
- simulation-state commits: `0`
- weight updates: `0`

The canonical archive passed both gzip integrity and tar listing verification. The preservation manifest verified `summary.json`, `details.json`, and stdout.

## Primary result

### Rank-1 action distribution

`C00 = BASE prefill -> BASE selector`

- total-rank-1: `SEND 160/160`
- mean-rank-1: `SEND 160/160`
- total second-best: `WAIT 160/160`

`C10 = FA prefill -> BASE selector`

- total-rank-1: `WAIT 160/160`
- mean-rank-1: `WAIT 160/160`
- total second-best: `SEND 160/160`

Thus the prefill intervention flips the fixed BASE selector from a universally SEND-dominant regime to a universally WAIT-dominant regime across all 160 frozen contexts. The result is not explained by branch-length normalization because total and mean rankings agree exactly.

### WAIT-versus-best-non-WAIT margin

The preregistered `nda_total_margin` is `WAIT total score - best non-WAIT total score`.

Median margins by context:

| Context | C00 | C10 |
|---|---:|---:|
| MESSAGE_RECEIVED | -0.25390625 | 0.37109375 |
| OWN_PROPOSAL_PENDING | -0.25 | 0.869140625 |
| PROPOSAL_RECEIVED | -0.375 | 0.75 |
| QUIET | -0.87109375 | 0.99609375 |
| RECENT_INTERACTION | -1.37890625 | 0.498046875 |

Every C00 context remains on the non-WAIT side of the boundary and every C10 context remains on the WAIT side.

## Context sensitivity under C10

C10 rank-1 remains `WAIT 160/160`, but context changes move the raw action-score geometry. Relative to matched QUIET cases:

- `MESSAGE_RECEIVED`: median total deltas `SEND +0.375`, `PROPOSE +0.75`, `ACCEPT +0.40625`, `REJECT +0.5`, `WAIT -0.17578125`; median NDA-margin delta `-0.5625`.
- `RECENT_INTERACTION`: median total deltas `SEND +0.26953125`, `PROPOSE +0.34375`, `ACCEPT -0.015625`, `REJECT +0.125`, `WAIT -0.134765625`; median NDA-margin delta `-0.37890625`.
- `PROPOSAL_RECEIVED`: lower-order total ranking changes occur in `6/32` matched cases, while rank-1 changes occur in `0/32`.

The preregistered automatic tag `RANK_CONTEXT_SENSITIVE` is therefore driven by lower-order rank movement, not by a C10 top-1 action change.

Bounded interpretation: context-dependent action evidence remains present under C10, while the FA-prefill intervention establishes a globally WAIT-dominant rank-1 regime.

## C10 versus C00 intervention effect

For every frozen context class, `total_rank1_change_count = 32/32`; aggregate `160/160`.

Representative median C10-minus-C00 total-score shifts:

- QUIET: `WAIT +1.22265625`, `SEND -0.64453125`, `PROPOSE -1.40625`, `ACCEPT -2.890625`, `REJECT -2.34375`.
- RECENT_INTERACTION: `WAIT +1.314453125`, `SEND -0.58203125`, `PROPOSE -1.0`, `ACCEPT -2.4140625`, `REJECT median -1.65625`.

This supports causal localization to the WORLD-prefill intervention while the selector state is held BASE in both conditions. It does **not** yet localize the effect to a transformer layer, residual stream, attention head, MLP, or specific cached tensor.

## Exact repeat

Both C00 and C10 exact repeats were bit-for-bit/serialization identical at the stored-record level:

- `serialized_equal = true`
- `structural_mismatch_count = 0`
- total-score max absolute repeat delta = `0.0`
- mean-score max absolute repeat delta = `0.0`

## Token-count caveat

For C10, all five branch labels use exactly two scored branch tokens. For C00, WAIT/SEND/PROPOSE/ACCEPT use two tokens; REJECT uses two or three depending on case.

Large positive C10-minus-C00 REJECT total-score shifts in several `RECENT_INTERACTION` cases (approximately `+13.4` to `+13.7`) coincide with this branch-token-count difference and must not be interpreted as a semantic FA effect from total log-probability alone. The main SEND-versus-WAIT result is unaffected: both branches use two tokens and both total and mean rank-1 flip `160/160`.

## Scientific conclusion

The canonical P2-D1 result establishes the following bounded claim:

> FA WORLD-prefill causally moves the fixed BASE selector from a universally SEND-dominant decision regime to a universally WAIT-dominant decision regime across the frozen cohort, while measurable context-dependent action evidence remains beneath that rank-1 boundary.

The frozen P2 behavioral-admission result remains unchanged: `C10_NOT_BEHAVIORALLY_ADMITTED`.

## Next experiment

The next study should localize the causal mediator of the SEND-to-WAIT regime shift inside the prefill computation. The preferred design is preregistered coarse-to-fine causal activation/cache patching with bidirectional rescue/induction tests, while preserving the D1 cohort and using `SEND - WAIT` (or equivalently the sign-inverted WAIT margin) as the primary mediator readout.