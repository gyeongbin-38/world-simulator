# ARC-620 — Observatory Research Views

**Status:** DRAFT / O0  
**Parent:** ARC-600  
**Question:** Which researcher-facing views may the Observatory expose, and what semantics must those views preserve?

## Primary interaction model

The Observatory is optimized for inspection, not control.

The center of the application is always the world/relation canvas. Supporting information appears in collapsible and resizable panels so the researcher can recover maximum visual area when needed.

Required panel behavior:

- left navigation/layer panel: collapsible;
- right agent/evidence inspector: collapsible and resizable;
- bottom timeline/event panel: collapsible and resizable;
- lineage view: dockable or full-canvas mode;
- every hidden panel must be recoverable without reloading the run;
- panel state is local presentation state only.

## Core views

### World / Relation View

Purpose: inspect the current committed population and interaction topology.

Before a causal 2D-space experiment exists, node coordinates are presentation layout only.

The UI must visibly distinguish this state, for example:

```text
Network layout — not physical space
```

No viewer may infer physical distance, visibility, or interaction opportunity from screen distance in EXP-000.

Possible layers:

- display names;
- canonical IDs;
- committed message edges;
- committed proposal edges;
- lineage edges;
- birth/death markers;
- registered analysis overlays;
- future resource layer only after the resource intervention architecture exists.

### Agent Inspector

Selecting an agent should expose a traceable researcher view including, when available:

- display name;
- canonical `AgentId`;
- sprite portrait;
- alive/dead state;
- birth/death tick;
- founder/generation identity;
- canonical parents/children;
- recent committed interactions;
- current/last committed action facts;
- parse/rejection status;
- exact ContextPack/evidence/artifact references;
- exact raw-generation evidence on explicit expansion;
- experiment/model/treatment identifiers relevant to that cognition attempt.

Display name and sprite are presentation metadata. Canonical ID and immutable evidence remain the research anchor.

### Lineage / Genealogy View

The lineage view is a first-class research view.

It must support:

- ancestor tree from a selected agent;
- descendant tree from a selected agent;
- founder-root view;
- parent/child edge inspection;
- generation-depth labels;
- birth/death tick;
- clickable sprite thumbnail plus canonical ID;
- exact jump from lineage node to Agent Inspector.

Lineage edges come only from canonical reproduction/birth facts.

The UI must not treat biological/genealogical relation as social knowledge or social affinity.

Neutral measured values such as descendant count may be shown. Interpretive labels such as `dominant`, `fit`, `elite`, or `successful` require a registered post-hoc analysis and must be marked derived.

### Timeline / Event View

Required controls:

- play;
- pause;
- step backward in replay;
- step forward;
- seek to tick;
- presentation speed;
- event-type filter.

Changing replay time never changes canonical run state.

Event filters should include at least:

- messages;
- proposals/accept/reject;
- births;
- deaths;
- rejected model outputs;
- infrastructure/censoring outcomes where applicable.

### Evidence View

The evidence view exists for paper-grade auditability.

From an observed action/interaction, a researcher should be able to resolve:

```text
run/tick/agent
  -> committed behavior/event
  -> validation/parse identity
  -> raw model generation
  -> rendered input / ContextPack
  -> model/adapter/treatment/generation-policy identity
```

The UI should distinguish canonical facts, raw evidence, and derived interpretation visually.

### Experiment Metadata View

At minimum expose:

- run/experiment ID;
- run status;
- code commit;
- model/profile identity;
- adapter identity;
- interface treatment;
- generation policy/seed identity;
- founder count;
- tick range;
- resource condition;
- intervention condition;
- replay vs live state;
- exploratory vs confirmatory label when available.

## Display names

Display names exist only for researcher readability.

Rules:

- one unique display name per agent within a run;
- deterministic under a frozen Observatory naming configuration;
- neutral synthetic names rather than role/personality-coded titles;
- hidden from agents in EXP-000;
- never used as canonical keys;
- canonical `AgentId` remains visible in detailed inspection/export.

A display name change under a new visualization configuration must not change any scientific run identity or result.

## Sprite identity

Exact sprite semantics are owned by `docs/observatory/SPRITES.md`.

ARC-620 only requires that:

- every living agent be visually distinguishable;
- sprite identity be deterministic and researcher-only in EXP-000;
- the initial default be `V0 — Independent visualization`;
- visual lineage mode `V1` be optional presentation-only and off by default for baseline screenshots unless explicitly enabled/labeled;
- no sprite field enter model context or canonical simulation law.

## Layout semantics

Graph layout algorithms may use canonical relations to improve readability, but their output is presentation metadata.

Examples allowed for layout only:

- force-directed relation layout;
- lineage tree layout;
- stable seeded jitter to avoid node overlap;
- clustering for readability based on a registered derived graph.

The canvas must not visually imply unsupported causal claims. If layout uses an analysis-derived grouping, that fact should be inspectable.

## Panel and focus state

The following are browser/client-local state unless explicitly exported as a presentation preset:

- open/closed panels;
- panel width/height;
- selected agent/event;
- hover state;
- zoom/pan;
- layer visibility;
- timeline presentation speed.

None may be serialized into canonical snapshots.

## Paper-oriented export

A future figure/screenshot export should embed or accompany enough provenance to recover:

- run ID;
- tick/state version;
- snapshot/frame digest;
- view/projection version;
- active analysis overlays;
- visual configuration ID;
- canonical IDs for highlighted agents.

A figure is presentation, not numerical authority, consistent with DF-260.

## Design system

Visual styling is owned by `docs/observatory/DESIGN_SYSTEM.md`.

The styling system is subordinate to scientific legibility. Animation must visualize committed facts only, and all essential information must remain available with motion disabled.

## Acceptance tests

Before O0 implementation is considered admitted:

- all primary panels can collapse without losing run state;
- world canvas expands when surrounding panels collapse;
- display names remain unique/stable for a fixed configuration;
- changing display names/sprites/panel layout leaves canonical hashes/context unchanged;
- genealogy exactly matches canonical parent-child facts;
- non-spatial network layout is labeled non-physical;
- evidence drill-down resolves immutable references;
- headless run behavior is unchanged with Observatory absent.
