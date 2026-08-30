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

## V0 morphology contract

The first implementation deliberately starts small:

```text
body
+ head
+ eyes
+ palette / small geometric variation
-> sprite
```

The design language should remain simple while the combinatorial space is large.

V0 trait families may include:

### Body
- archetype/shape;
- width/height ratio;
- scale;
- small contour variation;
- primary/secondary color slots;
- optional simple surface pattern.

### Head
- archetype/shape;
- width/height ratio;
- scale;
- vertical/side offset within bounded limits;
- color/tint relationship to the body.

### Eyes
- archetype/shape;
- size;
- spacing;
- vertical offset;
- optional asymmetric micro-variation;
- iris/eye color where the style supports it.

Future appendages, horns, antennae, tails, mouths, or decorations are optional expansion slots. They are not required for V0 diversity.

## SpriteIdentity concept

A presentation record should contain a deterministic `SpriteRecipe` rather than a scientific/neural `genome` object.

Example conceptual fields:

```text
sprite_schema_version
visual_seed
body_shape
body_width
body_height
head_shape
head_width
head_height
eye_shape
eye_size
eye_spacing
eye_offset
primary_hue
secondary_hue
pattern_variant
micro_variation_seed
phenotype_signature
```

`SpriteRecipe` terminology is preferred so presentation inheritance is not confused with ARC-350 neural genotype/heredity.

Generation is deterministic from run visualization identity plus stable agent creation identity.

Operational timing, screen order, GPU order, transport timing, or random UUID bits must not define appearance.

Same run + same visualization configuration should reproduce the same agent appearance.

## External generation-method reference

The implementation may take its procedural-generation pattern from:

```text
williamsharkey/paracharacter
reference commit: 83d5de4b143cfa06ce31e452b8ffc8eb404a811b
```

The useful pattern is:

- modular part categories;
- seeded deterministic generation;
- explicit custom part selection;
- renderer separated from character recipe.

Its package metadata declares MIT licensing at the referenced repository state.

WORLD must not depend on its specific character art. No third-party art asset or source code should be vendored until its exact license/provenance is recorded. The default plan is to implement the small deterministic recipe/composition mechanism in WORLD and use original WORLD sprite parts.

## Unique-by-construction

The renderer must not rely only on low collision probability.

Every assigned living-agent appearance receives a normalized `phenotype_signature`.

Deterministic assignment sequence:

1. derive initial visual seed from frozen visualization identity + stable agent creation identity;
2. generate `SpriteRecipe`;
3. normalize and hash the phenotype signature;
4. compare against assigned signatures in the relevant run/view configuration;
5. if identical or inside the configured near-duplicate threshold, derive deterministic collision salt `n+1`;
6. regenerate until admitted;
7. persist/cache only the final presentation identity.

The collision process cannot mutate simulation state.

For a frozen visualization configuration, assignment order must itself be deterministic (for example canonical agent-creation order), so replay reproduces the same identities.

## Near-duplicate criterion

Exact hash inequality is necessary but may not be visually sufficient.

V0 should define a deterministic presentation-only distance over features such as:

- body shape;
- head shape;
- eye shape;
- major size ratios;
- eye spacing;
- palette distance;
- pattern variant.

Two concurrently displayed agents that are too similar under the frozen threshold are re-derived by the deterministic collision rule.

This distance is a renderer/readability rule only. It is not a biological fitness or behavioral metric.

## Neutral art semantics

Avoid role-coded baseline designs such as:
- king;
- warrior;
- healer;
- elite;
- weakling;
- evil;
- worker caste;
- profession uniforms;
- social-rank marks.

Prefer neutral biological/abstract variation.

A shape or color must not imply a canonical personality or social role.

## Renderer

Initial implementation should use modular 2D composition rather than per-agent image generation:

```text
body layer
+ head layer
+ eye layer
+ bounded transforms
+ palette mapping
+ optional simple pattern
-> raster/vector sprite or cached atlas entry
```

This is preferred because it is deterministic, cheap, replayable, scalable, and lineage-friendly.

The implementation may use vector/SVG source parts and rasterize/cache them for the canvas; `sprite` here refers to the runtime 2D character representation, not necessarily hand-authored pixel art.

## Modes

### V0 — Independent visualization
EXP-000 baseline default:
- unique deterministic appearance;
- no visual inheritance;
- agents cannot see appearances;
- non-causal;
- all living agents are visually distinguishable under the configured threshold.

This is the default for baseline observation and paper screenshots unless another presentation mode is explicitly labeled.

### V1 — Researcher-visible visual lineage
Later presentation mode:
- child appearance recombines selected parent visual traits;
- optional deterministic visual mutation;
- sibling uniqueness remains enforced;
- agents still cannot see appearance;
- remains non-causal.

V1 exists to make genealogy easier for humans to read. It is not evidence of neural inheritance or behavioral inheritance.

### V2 — Causal visible morphology experiment
Separate experimental condition:
- appearance observations enter agent ContextPack;
- appearance can therefore influence decisions;
- requires explicit visibility/experiment architecture;
- is not EXP-000.

V1 must never silently become V2.

## Visual-lineage derivation in V1

If V1 is enabled, a child `SpriteRecipe` may derive bounded traits from canonical parent IDs plus deterministic presentation mutation.

Example presentation-only operator:

```text
child trait
= deterministic choose/interpolate(parent_A visual trait, parent_B visual trait)
+ bounded visual mutation(child creation identity)
```

The operator must be symmetric with respect to parent ordering unless the visual design explicitly defines a non-biological display convention.

Multiple children of the same parents must still receive unique admitted phenotypes through child identity + collision resolution.

## Visual vs neural inheritance

```text
visual lineage  = Observatory appearance
neural heredity = model/adaptor parameter inheritance
culture         = transmitted information
behavior        = observed phenotype
```

Visual similarity is not evidence of neural heredity, culture, fitness, mate preference, or social meaning.

## Animation

Possible event-following animations:
- idle;
- message;
- proposal;
- accept/reject;
- birth;
- death/fade.

Animations visualize committed facts. They never decide when a fact occurs.
