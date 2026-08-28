# A00 — A-LifeLM Architecture Constitution

**Status:** REVIEWED  
**Foundation gate:** F0

## Mission

> A-LifeLM is an instrumented artificial-life research platform for observing how minimally socially constrained, reproducing language-model agents communicate, choose partners, develop persistent interaction patterns, transmit information across generations, and respond to controlled experimental interventions.

A-LifeLM is not a game architecture. Visualization exists to make experimental phenomena inspectable; it does not own simulation rules or scientific truth.

## Foundation invariants

### INV-01 — Minimal imposed social priors
EXP-000 does not predefine friend, enemy, leader, team, profession, family role, trust score, cooperation reward, social rank, technology level, civilization objective, or personality assignment.

### INV-02 — Canonical experiment state is authoritative
Canonical run/agent/lifecycle/message/proposal/intervention/lineage state is owned by A-LifeLM-controlled state-transition mechanisms. Models, UI, analysis code, and external frameworks are not canonical authorities.

### INV-03 — Model independence
Foundation semantics do not depend on one model family, provider, inference framework, storage engine, or UI toolkit.

### INV-04 — Deterministic before probabilistic
Scheduling, eligibility, visibility, transition validation, ordering, hashing, and experimental bookkeeping are deterministic unless an experiment explicitly studies randomness.

### INV-05 — Context is compiled
No agent receives the global transcript, complete history, another agent's private state, or researcher-only information by default.

### INV-06 — Model output is a proposal
A model emits an `ActionIntent`; it cannot directly mutate canonical state.

### INV-07 — State/event atomicity
When a transition requires both canonical-state mutation and a domain event, they belong to one atomic commit boundary.

### INV-08 — Raw evidence is preserved
Raw model output and other required evidence are retained under immutable identity and referenced by later derived data.

### INV-09 — Observer is not simulator
The Observatory and analysis layers cannot directly change simulation state.

### INV-10 — Visualization is non-causal by default
Before an explicit physical-space experiment, sprite position, appearance, and screen proximity do not affect communication, reproduction, cognition, visibility, or survival.

### INV-11 — No central mate scoring
EXP-000 never selects reproduction partners using fitness, tournament selection, researcher compatibility, role, lineage label, mood, affect, or hormone-like values.

### INV-12 — Bilateral reproduction
A two-parent birth requires an agent-originated proposal and explicit matching acceptance plus only experiment-law eligibility.

### INV-13 — Lineage is not automatic social knowledge
Parent/child identity is researcher-visible but hidden from agents unless an explicit information channel exposes it.

### INV-14 — Birth does not copy experience
A child does not inherit parent transcripts, private memory, or cultural history by default.

### INV-15 — Death is terminal
A dead agent cannot generate new cognition, actions, or messages in that run.

### INV-16 — EXP-000 starts without resources
No food, currency, medicine, weapon-like object, tool, building, material, longevity item, resource economy, or technology tree exists initially.

### INV-17 — Interventions are explicit
Researcher-caused causal changes are versioned experimental interventions, not silent state edits.

### INV-18 — Exploration and confirmation are separate
Exploratory observations may generate hypotheses. Confirmatory evidence requires fresh confirmatory runs under frozen experimental/analysis rules.

### INV-19 — Replay and replication differ
Replay reconstructs a recorded run. Replication performs fresh inference under a reproduced experimental condition.

### INV-20 — Inference timing is not causality
Wall time, GPU completion order, thread order, batch position, retry count, or storage timing cannot decide simulated social causality.

### INV-21 — Capacity is censoring, not ecology
Infrastructure capacity must not silently reject births/actions or kill agents. Capacity-triggered termination is explicitly recorded as censoring/infrastructure outcome.

### INV-22 — No synthetic affect in EXP-000
Synthetic neuromodulation or affect is a later controlled experimental axis.

### INV-23 — Culture requires a transmission path
Claims of cultural persistence must identify how information moved across agents/generations.

### INV-24 — Emergent labels are post-hoc
Labels such as leader-like, coalition-like, attachment-like, aggression-like, science-like, or technology-like are analytical interpretations, not baseline state variables.

### INV-25 — Headless first
Every authoritative experiment must run without the graphical Observatory.

### INV-26 — Analysis is read-only
Derived datasets and metrics cannot rewrite historical canonical run state.

### INV-27 — Reproducibility metadata is first-class
Model/config/code/spec/seeds/scheduler/sampling/intervention identities required to interpret a run are preserved.

### INV-28 — External components are disposable
Replacing a model runtime, UI, storage adapter, or analysis library must not redefine foundation domain semantics.

### INV-29 — Context Fabric principle
Raw data is stored once, deterministically reduced/indexed, selectively assembled into bounded context, and expanded by exact reference only when needed.

### INV-30 — Model-facing semantics are controlled
Internal researcher-readable action names need not be shown verbatim to the model. Model-facing affordance labels/descriptions are neutral, pinned, and treated as experimental treatment.

### INV-31 — Baseline memory is event-derived
EXP-000 has no hidden model-authored semantic journal. Agent-visible recent history is deterministically compiled from information that agent was allowed to observe.

### INV-32 — Randomness has causal identity
Confirmatory random streams derive only from frozen experiment/run/agent/opportunity identities, never operational timing artifacts.

### INV-33 — Scientific validity outranks presentation
Priority:
1. experimental validity/data integrity
2. correctness
3. reproducibility/recoverability
4. observability
5. compute efficiency
6. researcher ergonomics
7. visual polish

## Change rule

Breaking these invariants requires an explicit foundation-breaking architecture change. Attractive external code, a new paper, or implementation convenience alone is insufficient.
