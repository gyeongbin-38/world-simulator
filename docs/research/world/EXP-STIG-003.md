# EXP-STIG-003 — Persistence-necessary retention

Status: PRE-INFERENCE PROTOCOL / bounded exploratory pilot.

## Ownership and scope

This document owns the experimental extension to visible information and shared
state for EXP-STIG-003 only. EXP-000, EXP-STIG-001 and EXP-STIG-002 records,
schemas, semantics and evidence remain unchanged. Campfire is out of scope.
This is a fixed-population, four-tick laboratory assay, not a founder
admission, a long-horizon population claim, or a resource ecology.

The extension follows the existing Constitution, ARC-240, ARC-270 and SEQ-230:
model proposal -> strict parser -> deterministic validation against S_t ->
conflict resolution -> atomic SQLite/WAL state/event/evidence/outbox commit ->
S_(t+1). All contexts compile before any same-tick inference. The existing
filesystem CAS owns raw/context/trace bytes; no model text becomes an
executable instruction. Experiment state and tables live in a separate
database. The EXP-000 kernel and schema are not widened, and the EXP-STIG-002
instrumental world module is not modified; this experiment binds its own
world, affordance, runner and test modules by hash.

## Question

EXP-STIG-002 produced zero spontaneous TRACE bootstrap under mere instrumental
opportunity: TRACE could only publish what the actor already knew, so its
entire benefit accrued to other agents, while INSPECT resolved each missing
fact directly into persistent knowledge. Nothing ever required persistence.

This experiment removes that confound by making persistence instrumentally
necessary for the actor's own objective. The missing fact is observable only
as a private transient scan that never survives into the submission window.
A correct terminal answer is reachable only if the actor carried the scanned
value through a committed persistent channel.

## Matched conditions and mechanics

Three persistent identities X17, X29, X43; six facts:

F1=amber, F2=cedar, F3=violet, F4=umber, F5=onyx, F6=maple.

Fixed objectives:

- X17: {F1, F2}; knows F1; may scan F2.
- X29: {F3, F4}; knows F3; may scan F4.
- X43: {F5, F6}; knows F5; may scan F6.

Each missing fact is scannable only by its needer and is absent from every
other agent's knowledge, objective and scan set, so no peer can supply it.
Persistent knowledge contains initial facts and REUSE-acquired facts only.

Action inventory: WAIT and SEND in all conditions; INSPECT and SUBMIT in all
conditions; TRACE and REUSE additionally in B and C; COMMIT additionally in C.

Ephemeral scan boundary:

- INSPECT(fact_id) is afforded only for the actor's missing objective fact,
  while no active scan covers it, and only while the following tick precedes
  the submission tick. It costs one exploration unit and writes a private
  scan visible to that actor from the next tick.
- Scans never persist into the submission window: they are removed when the
  final tick is committed into existence and are absent from every tick-T
  context. A scan expiring unused is a measured cost, not a failure.
- While a scan is visible, TRACE and COMMIT may capture its fact_id with the
  exact scanned value, under the same value-equality validation as persistent
  knowledge.

Submission window:

- The final tick is the submission window: its afforded action set is exactly
  {WAIT, SUBMIT}. SUBMIT is never afforded earlier; a parser-valid early
  SUBMIT is recorded as an affordance rejection and commits nothing.
- SUBMIT remains free-form text scored by exact match against the objective
  answer format. Correctness is a property of the submitted text only.

Treatments:

- A — MESSAGE ONLY: WAIT, SEND, INSPECT, SUBMIT.
- B — PERSISTENT TRACE: A plus TRACE and grounded REUSE.
- C — CAUSAL WORLD: B plus grounded COMMIT.

Consequence: at the submission tick the missing fact can be present in an
actor's context only via (i) a committed trace, (ii) a committed world_state
entry in C, or (iii) a peer message relaying the actor's own earlier scan,
which requires another agent to voluntarily return the value and cannot be
self-served because self-send is prohibited. Channel (iii) exists in every
condition and is measured separately; it is the only non-environmental route.

Everything else is unchanged from the grounded-affordance boundary: SEND
targets a different active agent with bounded free text; new messages, traces
and world writes become visible at t+1 only; one strict JSON object per
opportunity; malformed output consumes the opportunity without substitution;
backend faults abort and censor the run.

## Frozen design before any model forward

specs/experiments/EXP-STIG-003-v1.yaml owned exact sizes, seeds, values,
presentation and interpretation parameters for the first pilot, whose
execution overlay was specs/experiments/EXP-STIG-003-execution-pilot.yaml,
digest-bound to the scientific configuration. The bounded pilot executed one
world per condition, three agents, four ticks: 36 real-model opportunities.

After the v1 pilot completed, specs/experiments/EXP-STIG-003-v2.yaml
superseded it with the execution overlay
specs/experiments/EXP-STIG-003-execution-pilot-v2.yaml; after the v2 pilot
completed, specs/experiments/EXP-STIG-003-v3.yaml superseded it with
specs/experiments/EXP-STIG-003-execution-pilot-v3.yaml. Each version's record
and evidence remain authoritative for its own configuration.

Two locally resident distinct instruction-model families use unchanged pinned
Q8 artifacts; per-condition assignment is [OLMo, Villanova, OLMo]. Greedy
deterministic completion (temperature 0, top_k 1, top_p 1, min_p 0, repeat
penalty 1, n_predict 128) uses the same mechanical renderer for both models
with no system instruction, chat template, history replay or Astra. The
grounded affordance grammar narrows proposals to currently executable actions
and visible references; Gateway/kernel validation remains authoritative. No
retries, repair or fallback. All model files, code/spec hashes and runtime
executable hashes bind a pre-execution manifest before generation. No
threshold, model setting, horizon or label changes after observing results.

## Preregistered outcomes

- P0 — no persistence act: zero committed TRACE/COMMIT captures a scanned
  objective fact; necessity alone still yields no bootstrap. Bounded
  negative; the pilot stops.
- P1 — bootstrap: at least one committed TRACE or COMMIT captures a scanned
  objective fact while it is only scan-known.
- P2 — reuse: at least one voluntary REUSE of a committed trace, self or
  foreign.
- P3 — completed chain: at least one correct terminal SUBMIT whose missing
  objective facts all carry environmental provenance (a committed trace, a
  C world_state entry, or trace content internalized through REUSE).
  Provenance is audited mechanically from the recorded tick-3 visible state;
  no re-inference.
- P4 — replication: P1 and P3 each occur under both model families.

Controls and classification:

- Condition A has no environmental persistence channel, so a correct A
  submission can arise only via peer relay. Relay completions are counted
  separately and never toward P3. A correct A submission with unexplained
  provenance voids the affected world pending evidence audit; it is a
  protocol anomaly, never a scientific claim.
- A verified submission additionally requires every objective fact to be in
  the actor's persistent knowledge at the submission tick (REUSE
  internalization). Raw correctness and verified correctness are both
  reported; their gap measures whether models read back from the environment
  without internalizing.
- Premature SUBMIT attempts, expired unused scans, relay-classified messages,
  non-objective traces, foreign REUSE attempts, exploration cost, the full
  action funnel and per-model splits are all reported including zeros.
  Deterministic test agents never contribute to empirical metrics.

## Version 2 amendment

The v1 pilot completed as a bounded negative (P0). Two instrument defects
were isolated from the behavioral record before any v2 inference:

- TRACE and COMMIT admitted every currently held fact (persistent knowledge
  union active scans), so "persist the ephemeral observation" was
  indistinguishable from "persist something already durable". All four C
  COMMITs bound already-known facts while scans were active.
- The SUBMIT answer was a free-form field described as "objective answer,
  text at most 256 characters". All six submissions emitted that descriptor
  verbatim, so answer production was censored at the interface layer
  regardless of what the actor knew.

v2 changes the proposal surface only; world law, kernel validation, model
cohort, seed schedule, sizes and stop rules are unchanged:

- TRACE fact_ids are restricted to facts covered by an active scan, and
  TRACE is not afforded without one. Any TRACE proposal is therefore a
  retention act on an ephemeral observation by construction. COMMIT keeps
  the v1 known-or-scanned domain, so in C the TRACE/COMMIT choice itself
  measures targeting.
- The SUBMIT answer is grammar-constrained to the actor's objective
  skeleton (e.g. F1=<word>|F2=<word>) and the affordance descriptor carries
  the concrete answer_format. Structure is enforced; values still come from
  the model's context, and mechanical provenance classification is
  unchanged.

The v2 pilot completed with a P1 event but all submissions echoed the
template tokens. v3 then grammar-grounded each answer slot to the fact
values actually visible to the actor at the submission window (persistent
knowledge union committed trace values union, in C, committed world_state
values): an unpersisted missing fact's value is un-emittable, so slot
correctness and provenance coincide by construction, and the peer-relay
route can no longer produce a correct answer (A becomes a pure negative
control). All other mechanics are unchanged from v2.

## Stop rule

The pilot is bounded at 36 opportunities. No larger run is authorized unless
at least one P1 event occurs or another scientifically justified signal is
recorded in the sealed result receipt.

## Execution gate and durability

Before real inference, deterministic validation must cover all conditions,
strict schemas, the scan expiry boundary, the submission window, same-tick
isolation, completion-order invariance, conflicts, malformed output,
missing/tampered CAS, precommit rollback, postcommit restart/idempotency and
replay reconstruction. A controlled capability fixture must demonstrate one
full INSPECT -> TRACE -> REUSE -> SUBMIT chain per persistent treatment. A
passing validation receipt binds the executed source tree and protocol.
Final replay revalidates raw proposals, events, state hashes, required CAS
and outbox against every boundary. Immutable result receipts bind databases,
CAS evidence, runtime provenance and analysis. Partial runs cannot be
COMPLETE. Recovery uses durable prepared attempts without new cognition. No
automatic behavioral retries are allowed.
