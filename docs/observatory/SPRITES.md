# Observatory Sprite Identity

**Scope:** researcher-facing presentation.  
**EXP-000 causality:** none.

## Goal

Every living agent should appear as a visually distinct original artificial organism.

The art direction may take high-level inspiration from collectible-creature systems such as Axie Infinity:
- compact readable creature silhouettes;
- modular visible traits;
- strong individual identity;
- enough combinatorial diversity for populations;
- potential for visually readable lineage later.

Do not copy existing characters, exact body parts, proprietary artwork, trademarked designs, or palettes.

## EXP-000 rule

```text
sprite appearance
!= agent-visible information
!= mate preference input
!= behavioral trait
!= lifecycle law
```

The Simulation Kernel must not query presentation traits in EXP-000.

## SpriteIdentity concept

A presentation record may include:

```text
visual seed
body archetype/shape
eyes
ears/fins/antennae
crest/horn variant
mouth
tail
surface pattern
palette
scale
small decoration
```

Generation is deterministic from run visualization identity plus stable agent creation identity.

Operational timing, screen order, GPU order, or random UUID bits must not define appearance.

Same run + same visualization configuration should reproduce the same agent appearance.

## Unique-by-construction

The renderer should avoid near-duplicate living agents.

A deterministic presentation-only collision process may:
1. generate a visual signature;
2. compare it with currently assigned signatures;
3. derive another variant if too similar;
4. store the final presentation identity.

This process cannot mutate simulation state.

## Neutral art semantics

Avoid role-coded baseline designs such as:
- king;
- warrior;
- healer;
- elite;
- weakling;
- evil;
- worker caste.

Prefer neutral biological/abstract variation.

## Renderer

Initial implementation should use modular 2D composition:

```text
body
+ eyes
+ appendages
+ crest/horn/antenna
+ tail
+ pattern
+ palette mapping
+ optional decoration
→ sprite
```

This is preferred over generating a new AI image at every birth because it is deterministic, cheap, replayable, scalable, and lineage-friendly.

## Modes

### V0 — Independent visualization
EXP-000 baseline:
- unique deterministic appearance;
- no visual inheritance;
- agents cannot see appearances;
- non-causal.

### V1 — Researcher-visible visual lineage
Later presentation mode:
- child appearance recombines selected parent visual traits;
- optional deterministic visual mutation;
- agents still cannot see appearance;
- remains non-causal.

### V2 — Causal visible morphology experiment
Separate experimental condition:
- appearance observations enter agent ContextPack;
- appearance can therefore influence decisions;
- requires explicit visibility/experiment architecture.

V1 must never silently become V2.

## Visual vs neural inheritance

```text
visual lineage  = Observatory appearance
neural heredity = model/adaptor parameter inheritance
culture         = transmitted information
behavior        = observed phenotype
```

Visual similarity is not evidence of neural heredity or social meaning.

## Animation

Possible event-following animations:
- idle;
- message;
- proposal;
- accept/reject;
- birth;
- death/fade.

Animations visualize committed facts. They never decide when a fact occurs.
