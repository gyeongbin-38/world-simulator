# EXP-STIG-004 — Stigmergic Persistence Dependence

## Status

COMPLETE. The v1 pilot and the authorized 144-opportunity larger run both
executed, replayed, and audited PASS under this configuration; sealed results
live in docs/research/world/EXP-STIG-004-results.md. P1o and P1s supported
under OLMo; P2/P3/P3o/P4 not met; TRACE selection zero across all worlds.

This experiment extends EXP-STIG-003. The EXP-STIG-003 lineage (v1 bounded
negative, v2 first P1, v3 first P3, authorized 144-opportunity run replicating
P1/P3 under OLMo only) remains authoritative for its own evidence.

## Motivation

EXP-STIG-003 established that a local model voluntarily persists a scanned
objective fact into canonical world state when persistence is the only route
to its own correct answer — self-serving persistence. It also produced a
strong bounded negative for the TRACE channel: models chose canonical COMMIT
when available and nothing when only TRACE existed.

The original stigmergy question remains unmeasured: whether an agent will
persist information that benefits another agent's objective — other-serving
environmental persistence. EXP-STIG-004 makes mutual dependence the only
route: each dependent agent's missing fact is scannable only by its peer, and
under the value-grounded answer grammar a peer SEND cannot inject a value into
the needer's answer options. Environmental persistence is the sole channel by
which a scanned value can reach another agent's submission grammar.

## World

Three persistent identities: X17, X29, X43. Four ticks 0..3; SUBMIT is
afforded only inside the terminal submission window at tick 3. Private scans
expire when the window opens. Facts and values are unchanged from
EXP-STIG-003:

- F1=amber, F2=cedar, F3=violet, F4=umber, F5=onyx, F6=maple.

Objectives, initial knowledge, and scannable sets:

- X17: objective F1=v|F2=v; initially knows F1; scannable set {F4}.
- X29: objective F3=v|F4=v; initially knows F3; scannable set {F2}.
- X43: objective F5=v|F6=v; initially knows F5; scannable set {F6}.

X17's missing F2 is scannable only by X29; X29's missing F4 is scannable only
by X17. X43 retains the EXP-STIG-003 self-sufficient shape as a within-run
replication arm. No agent can scan its own missing fact unless its peer
carries it; no objective fact appears in another agent's initial knowledge.

### Agent-visible information change

Relative to EXP-STIG-003, each agent's visible data additionally carries a
public objective board and sensor map: every agent's objective fact_ids and
every agent's scannable fact_ids. No fact values, traces, knowledge, or scans
of other agents are visible. This change is authorized by this document under
the architecture-change rule for agent-visible information; the EXP-STIG-003
world is unchanged and its evidence remains reproducible.

### Conditions

- A — MESSAGE ONLY: WAIT, SEND, INSPECT, SUBMIT; no environmental persistence.
- B — PERSISTENT TRACE: A plus TRACE (scan-covered facts only) and grounded
  REUSE.
- C — CAUSAL WORLD: B plus COMMIT of known or scanned facts into canonical
  world state.

Under the value-grounded answer grammar (unchanged from EXP-STIG-003 v3),
SUBMIT answer slots draw only from values visible at the window: persistent
knowledge union committed trace values union, in C, committed world_state
values. Message text contributes no options, so a SEND relay cannot produce a
correct dependent-objective answer; condition A is a pure negative control.

## Preregistered outcomes

- P0 — no committed TRACE or COMMIT captures any scanned fact across all
  opportunities.
- P1s — self-serving persistence: at least one committed TRACE or COMMIT
  captures X43's scanned missing fact (within-run replication of the
  EXP-STIG-003 finding).
- P1o — other-serving persistence: at least one committed TRACE or COMMIT
  captures a scanned fact needed by a peer (F4 by X17, or F2 by X29). This is
  the primary stigmergic measurement.
- P2 — at least one voluntary REUSE of a committed trace, self or foreign.
- P3 — at least one correct terminal SUBMIT whose missing objective facts all
  carry environmental provenance, established mechanically without
  re-inference.
- P3o — a correct submission on a dependent objective (X17 or X29) with
  environmental provenance — a completed cross-agent stigmergic chain.
- P4 — P1o occurs under both model families.

Controls and classification follow EXP-STIG-003: relay-classified messages
are reported separately, unexplained correct submissions void the affected
world pending audit, verified-vs-correct gap measures REUSE internalization,
and all funnel counts including zeros are reported.

## Stop rule

The pilot is bounded at 36 opportunities (one world per condition, three
agents, four ticks). No larger run is authorized unless at least one P1o
event occurs or another scientifically justified signal is recorded in the
sealed result receipt.

## Authorized larger run (version 1.0.0-run)

The v1 pilot recorded a P1o event, so the stop rule admits a larger run.
specs/experiments/EXP-STIG-004-run-v1.yaml fixes that run's size and
assignment before execution; world law is unchanged from v1 and the v1
scientific configuration remains the world-law authority. The run executes 4
worlds per condition (144 opportunities) with alternating per-world model
assignment [[0,1,0],[1,0,1],[0,1,0],[1,0,1]] so each model family covers both
serving directions and the self-serving arm, a fresh seed schedule disjoint
from the pilot, and the same P0/P1s/P1o/P2/P3/P3o/P4 outcome definitions. A
secondary preregistered measurement is the TRACE selection frequency across
all active-scan windows. The run is a single replication study, not an
iterated search; no further size increase is implied.

## Execution gate and durability

Before real inference, deterministic validation must cover all conditions,
strict schemas, the scan expiry boundary, the submission window, same-tick
isolation, completion-order invariance, conflicts, malformed output,
missing/tampered CAS, precommit rollback, postcommit restart/idempotency and
replay reconstruction, plus the new surface: peer-objective visibility,
cross-scannable INSPECT, and a cross-agent capability fixture demonstrating
INSPECT → TRACE → foreign REUSE → SUBMIT in B and INSPECT → COMMIT → foreign
SUBMIT in C. The runner must refuse to execute when the qualification receipt
is absent, stale, or failed; when bound artifacts differ from their frozen
hashes; or when output evidence already exists. Infrastructure failures
censor the opportunity; they are never behavioral data.

## Frozen design before any model forward

specs/experiments/EXP-STIG-004-v1.yaml owns exact sizes, seeds, values,
presentation and interpretation parameters; its execution overlay
specs/experiments/EXP-STIG-004-execution-pilot.yaml is digest-bound to it.

Two locally resident distinct instruction-model families use unchanged pinned
Q8 artifacts; per-condition assignment is [OLMo, Villanova, OLMo], so the
mutual dependence pair tests other-serving persistence in both family
directions (X17/OLMo serves X29/Villanova via F4; X29/Villanova serves
X17/OLMo via F2) while X43/OLmo carries the self-serving control. Greedy
deterministic completion (temperature 0, top_k 1, top_p 1, min_p 0, repeat
penalty 1, n_predict 128) uses the same mechanical renderer for both models
with no system instruction, chat template, history replay or Astra. The
grounded affordance grammar narrows proposals to currently executable actions
and visible references; Gateway/kernel validation remains authoritative. No
retries, repair or fallback. All model files, code/spec hashes and runtime
executable hashes bind a pre-execution manifest before generation. No
threshold, model setting, horizon or label changes after observing results.
