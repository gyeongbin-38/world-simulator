# WORLD EXP-000 Soak Result V1

Status: **EXECUTED / AUDIT PASS**

## 1. Scope

This record freezes the result of `WORLD_EXP000_SOAK_V1`, the
durability/restart/replay soak named as the third next-engineering-stage item
in `WORLD_EXP000_CLOSURE_V1` ("run longer durability/restart/replay soak tests
without introducing new causal variables").

The soak drives the already-admitted LIVE EXP-000 composition — deterministic
kernel, `ContextCognitionPipeline`, SQLite durable store, CAS artifacts,
replay reader, and `LiveExperimentController` — with a deterministic
hash-driven policy runtime (`SoakPolicyRuntime`). It measures infrastructure
behavior only. It introduces no new causal variable and performs no model
reseeding, fallback, repair, action masking, or reseeding of committed
boundaries.

Owner semantics under verification:

- `SEQ-250` — crash recovery, commit ambiguity, and resume semantics
  (`commit not durably confirmed -> S_t`; `commit durably confirmed -> S_(t+1)`;
  no canonical `S_t+0.5`; lookup-first retry by deterministic `commit_id`;
  no model recall for an already committed boundary; capacity censoring is an
  explicit terminal outcome, not an infrastructure failure);
- `ARC-270` — durable commit/evidence/outbox/snapshot/replay boundary;
- `SEQ-230` — deterministic `S_t -> S_(t+1)` ordering across restarts.

This record establishes an engineering integrity result, not a claim about
agent behavior.

## 2. Execution identity

- study ID: `WORLD_EXP000_SOAK_V1`
- run ID: `WORLD_EXP000_SOAK_V1_R1`
- harness: `tools/world_exp000_soak.py`
- bounded test suite: `tests/live/test_exp000_soak.py`
- founders: `SOAK_F0`, `SOAK_F1`, `SOAK_F2`, `SOAK_F3`
- horizon: `48` ticks
- lifespan: `30` ticks
- maturity delay: `0`
- refractory interval: `4`
- population capacity: `18`
- context policy: `ContextPolicy.exp000`, max prior visible records `8`
- policy runtime: `SoakPolicyRuntime` — SHA-256 roll over
  `(seed | run_id | tick | actor)`; reads only visible `INCOMING_PROPOSAL`
  records and the peer directory; decisions are identical across process
  restarts
- evidence root: `E:\WORLD\AI_CACHE\evidence\EXP000_SOAK_V1` (sealed,
  write-once manifest)

## 3. Soak phases

1. **baseline** — uninterrupted run to terminal status; per-boundary state
   hash series recorded from the durable commit chain.
2. **restart-every-tick** — the store is closed and the run is resumed from
   durable state after every committed boundary; each resume must load the
   exact boundary hash committed by the previous process generation.
3. **fault sweep** — each commit-path fault point `F5..F10` is armed once at
   tick `12`, in both recovery modes:
   - `inprocess` — retry on the same in-memory run (the durable committer
     resolves either a rolled-back attempt via a fresh same-`commit_id`
     commit, or an acknowledged-lost commit via lookup + local publish);
   - `restart` — close the store, reopen, resume from the durable boundary,
     then continue.
4. **replay** — the full durable chain is replayed without model inference;
   verified commit count must equal the durable commit count and the
   replayed final state hash must equal the live final hash.
5. **call audit** — the shared runtime call log must contain exactly one
   `(tick, actor)` entry per cognition opportunity for the baseline and
   every-tick-restart phases (no re-cognition of a committed tick).

## 4. Results

### Terminal trajectory

- final status: `CENSORED` at tick 43 (population capacity 18 reached —
  an explicit terminal outcome, not an infrastructure failure)
- durable commits: `43`
- replay-verified commits: `43`
- baseline event tally: `AgentBorn=17`, `AgentDied=5`,
  `MessageCommitted=76`, `ReproductionProposalCreated=56`,
  `ReproductionProposalAccepted=17`, `ReproductionProposalRejected=32`,
  `BirthCandidateRejected:MULTI_BIRTH_BOUNDARY_CONFLICT=5`,
  `RunCensoredCapacity=1`

The trajectory therefore exercised births, natural deaths, committed
messages, proposal creation/acceptance/rejection, multi-birth boundary
conflicts, and the capacity-censoring terminal transition — not only
idle ticks.

### Integrity checks (all true)

- `baseline_terminal` — terminal status is a legal explicit outcome
- `baseline_replay_all_commits` — replay verified every durable commit
- `baseline_replay_final_hash` — replayed hash equals live final hash
- `restart_trajectory_identical` — 43 restarts produced a byte-identical
  durable boundary series (all per-boundary state hashes and event-type
  sequences equal)
- `restart_replay_final_hash` — restart trajectory replays to the same hash
- `restart_resume_hashes_match` — every resume loaded exactly the hash the
  previous process generation committed
- `fault_boundaries_correct` — for `F5..F8` the durable boundary stayed at
  `S_12` (rollback); for `F9`/`F10` it was `S_13` (commit durably confirmed,
  acknowledgement lost) — matching SEQ-250 in both modes
- `fault_series_identical` — all 12 fault runs continued to a durable
  boundary series identical to baseline, with no duplicate commit
- `no_recall_baseline`, `no_recall_restart` — zero duplicate `(tick, actor)`
  cognition calls across both uninterrupted and restart-every-tick phases

### Manifest identity

- manifest: `soak-manifest.json`
- result digest: `26be1c2c99ad7d3191ee0b73a9dc70a6b0fe065ba7a3b6b842d37632c4cff84d`
- baseline final state hash: `e77a69f8d66102fc11df63c59b59e13f47628d391524b9bacbc090f5af2ba907`
- audit: `tools/world_exp000_soak.py --audit` → `PASS`
  (manifest digest, terminal status, replay final hash, commit count, and
  all integrity checks re-verified against the sealed evidence)

## 5. Bounded claim admitted

The admitted LIVE EXP-000 stack can execute a continuous multi-agent
trajectory in which:

- every committed boundary survives an immediate process restart with an
  identical durable state hash;
- a crash at any point of the commit path — before transaction begin, during
  state/event/outbox writes, after database commit but before
  acknowledgement, and before in-memory publication — resolves to exactly
  the SEQ-250-prescribed durable boundary and continues to an identical
  trajectory with no duplicate commit;
- the complete durable history replays to the recorded final state hash
  without any model inference;
- no committed tick is ever re-cognized, including across 43 consecutive
  process restarts (368 unique `(tick, actor)` cognition calls, zero
  duplicates);
- capacity censoring terminates the run as an explicit outcome and does not
  corrupt the boundary chain.

## 6. Claims not admitted

The soak does not establish:

- real-model trajectory durability (the policy runtime is deterministic;
  the F1-F4 model-inference failure points are exercised only through the
  commit-path seam);
- multi-process or multi-writer concurrency correctness (the controller is
  single-writer by design);
- arbitrary-horizon longevity beyond 48 ticks;
- recovery from storage corruption, media failure, or hostile mutation
  (replay detects these; it does not repair them);
- any agent-behavior claim.

These require separately scoped work.

## 7. Evidence

- `soak-manifest.json` — sealed study manifest (write-once, digest-verified)
- `boundary-hashes.json` — baseline per-boundary state hash series
- `baseline/`, `restart/`, `fault-*/` — per-phase `world.sqlite` + `cas`
  durable stores, each independently replayable
- tests: `tests/live/test_exp000_soak.py` (16 tests, bounded horizon)
