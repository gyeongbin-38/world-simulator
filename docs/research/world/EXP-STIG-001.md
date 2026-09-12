# EXP-STIG-001 — Persistent environmental traces

Status: PRE-INFERENCE PROTOCOL / bounded exploratory experiment family.

## Ownership and scope

This document owns the experimental extension to visible information and shared
state for EXP-STIG-001 only. EXP-000, its Snapshot/ActionIntent schemas, lifecycle,
reproduction, NullGenome, and all historical evaluations remain unchanged.
Campfire is out of scope. This is a fixed-population, four-tick laboratory assay,
not a founder admission, a long-horizon population claim, or a resource ecology.

The extension follows the existing Constitution, ARC-240, ARC-270 and SEQ-230:
model proposal -> strict parser -> deterministic validation against S_t ->
conflict resolution -> atomic SQLite/WAL state/event/evidence/outbox commit ->
S_(t+1). All contexts compile before any same-tick inference. Existing filesystem
CAS owns raw/context/trace bytes; no model text becomes an executable instruction.
Experiment-specific state and tables live in a separate database. The existing
EXP-000 kernel and database schema are not widened for this experiment.

## Matched conditions and mechanics

A permits WAIT and SEND. B additionally permits TRACE and REUSE. C additionally
permits SET. All conditions expose the same three initially empty opaque registers.
Only C may change their values. No initial messages, traces, goals or solved tasks
are planted. All three agents are active throughout the horizon. There are no
births, deaths, rewards, resources, roles or personality fields in this assay.

TRACE appends arbitrary bounded text to the environmental catalog; REUSE copies
an existing visible trace into a new trace, preserving its content and ancestry.
SET writes bounded text into an existing register. An optional source trace must
be visible and its content must equal the proposed value. Conflicting same-tick
SETs to the same register are all rejected, even if their values match. No actor
wins a conflict by inference or storage order. SEND targets a different active
agent. New messages/traces/register changes become visible at t+1 only.

Every agent gets the whole bounded trace catalog in B/C; there is no ranking,
recommendation or forced encounter. Its own message history is visible, but other
agents' private messages are not. Register values and traces are environmental
text, never system instructions. One strict JSON proposal per opportunity;
malformed/illegal output consumes that opportunity without WAIT substitution,
retry or repair. Backend faults abort and censor the experiment.

## Frozen design before any model forward

The machine configuration in specs/experiments/EXP-STIG-001-v1.yaml owns exact
sizes, seeds, presentation and interpretation parameters. Three matched blocks
rotate model assignment across three opaque agents. Each block executes A/B/C;
each world lasts four ticks. Two locally resident, distinct instruction-model
families use unchanged Q8 files, pinned before execution. No adapter is trained.
Greedy direct completion uses the same mechanical renderer and settings for both
models; no helpful/cooperative/social system instruction or chat template is added.
No syntax constraint is used. Invalid outputs are legitimate observations.

Runtime loads may be grouped by model to fit local memory. Twelve GPU layers
are offloaded for each model on the available 3 GiB GTX 1050; remaining layers
stay on CPU. This placement is frozen before any inference, with no memory or
precision fallback after observation. Runtime or memory failure censors the run.
This never changes
contexts, seeds, opportunities or actor-sorted commit inputs. Each request resets
the prompt cache. Model identity is researcher-only. Same-tick agents see no
other same-tick output. All model files, code/spec hashes and runtime executable
hashes bind a pre-execution manifest before generation. No thresholds, model
settings, horizon or labels change after observing results.

## Causal stigmergy diagnostic

Primary observations alone cannot demonstrate that a trace caused behavior.
After the primary run, select the first trace-exposed opportunity per observer
per world (at most 27); selection depends on exposure only. Re-run its exact
prompt/seed/runtime once with traces removed, changing no other visible field.
This is a preregistered observer intervention, never committed or fed back into
primary runs, and is not a retry. Repeat the intact prompt once to test stability.
An attribution requires an identical intact repeat, a domain-valid primary and
counterfactual output, a changed action/payload, and an explicit foreign trace
use by REUSE or source-bound SET in the primary. Exclude any chain for which any
trace ancestor authored a prior directed message to the observer. Trace-copy
ancestry is traversed; third-agent reuse requires distinct creators/consumers.
Counterfactual validity is checked against the trace-removed visible state.

This identifies effects of trace availability at a particular decision, not a
whole-trajectory treatment effect or guaranteed semantic utility. No eligible
exposures means zero demonstrated stigmergic chains, not an imputed effect.

## Analysis and interpretation frozen before execution

Report communication per opportunity, created/reused traces, foreign reuse,
distinct subsequent consumers, repeated directed pairs, valid register changes,
duplicate text creation, descriptive per-agent action concentration, prompt and
completion tokens, requests and wall cost. These are observer-only. Specialization
is a descriptive concentration proxy at this horizon, never an assigned role.
Duplicate-work reduction is limited to fewer duplicate TRACE bodies; general
work/utility cannot be established without a preregistered external task objective.
Downstream utility is therefore reported as validated reuse and causal register
effects only, not as social value or intelligence.

Primary environmental-use rate is validated foreign REUSE/source-bound SET per
opportunity. A has zero environmental use by construction: B>A alone demonstrates
channel use, not causal stigmergy. S1 additionally requires a stable attributable
chain. S2 requires C>B on the use rate and at least one attributable source-bound
register change. Positive differences must occur in every matched block; equality
or mixed differences do not demonstrate superiority. S3 additionally requires
attributable chains in both observer model families and at least two blocks.
There is no significance claim with three blocks. Report all counts and paired
differences, including negative/zero results. S0 means no demonstrated effect;
it is not evidence of equivalence and is not a failed implementation.

Pre-registered labels: S0 A≈B≈C no demonstrated effect; S1 B>A persistent artifacts
provide bounded measurable value; S2 C>B additional causal consequences; S3
replication across heterogeneous models. Labels are hierarchical only when their
requirements pass. Insufficient exposures or poor codec competence limit inference
and cannot be repaired by prompt tuning. Deterministic test agents never contribute
to empirical metrics. Real-model failure is recorded separately from S0.

## Execution gate and durability

Before real inference, CPU validation must cover all conditions, strict schemas,
same-tick isolation, completion-order invariance, conflicts, malformed output,
missing/tampered CAS, precommit rollback, postcommit restart/idempotency, replay
reconstruction, and counterfactual isolation. A passing validation receipt binds
the executed source tree and protocol. Final replay revalidates raw proposals,
events, state hashes, required CAS and outbox against every boundary. Immutable
result receipts bind databases, CAS evidence, runtime provenance and analysis.
Partial runs cannot be COMPLETE. Recovery uses durable prepared attempts without
new cognition. No automatic behavioral retries are allowed.
