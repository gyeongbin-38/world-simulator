# WORLD Observatory Design System

**Scope:** researcher-facing UI presentation only.  
**Scientific authority:** none.  
**Single visual reference:** Liner-style restrained professional research UI, adapted to WORLD rather than copied as brand identity.

## Product character

WORLD Observatory should feel like a calm scientific instrument rather than a game HUD or entertainment dashboard.

Target qualities:

- quiet authority;
- strong information hierarchy;
- high density without visual noise;
- provenance always inspectable;
- generous canvas area;
- flat surfaces and hairline separation;
- minimal motion;
- one primary UI action color.

WORLD remains the product/brand name. External reference products are inspiration only.

## Core palette

### UI chrome

- **Action Green:** `#197b2e` — primary interactive emphasis only.
- **Forest Dark:** `#14371b` — major headings and strong labels.
- **Primary Tint:** `#edf3ed` — selected/active surface.
- **Canvas:** `#ffffff`.
- **Surface Light:** `#f9f9fa`.
- **Surface Alt:** `#f6f6f7`.
- **Ink:** `#1e1e1f`.
- **Muted:** `rgba(109, 109, 112, 0.8)`.
- **Border:** `rgba(109, 109, 112, 0.18)`.

Green is reserved for UI action/selection/focus. It is not a decorative background color.

### Scientific/content graphics exception

Agent sprites and scientific visualizations may use controlled multi-hue palettes because their colors represent presentation identity or data categories rather than UI actions.

Do not overload the UI action green with scientific meaning. Edge/event types should prefer shape, line style, labels, and restrained category colors over saturated decoration.

## Typography

Operational UI uses Pretendard Variable / Pretendard JP Variable where available.

Recommended hierarchy:

- app/run title: 24–32px, regular/medium;
- section heading: 17–20px, 500;
- body/UI: 14–16px, 400;
- button/interactive label: 14–15px, 500;
- evidence/hash/IDs: a legible monospaced stack.

Do not vendor or claim the proprietary/custom `Flare` typeface unless a valid license is explicitly available. A future open-licensed display serif may be approved separately; until then, operational UI remains sans-first.

## Geometry

- base spacing unit: 4px;
- common spacing: 4 / 8 / 12 / 16 / 20 / 24 / 40px;
- button/input radius: 8px;
- panel/card radius: 12px;
- pill controls: fully rounded;
- borders: 1px hairlines;
- shadows: avoid by default; use tinted surfaces for separation.

## Main shell

Desktop default:

```text
┌──────────────────────────────────────────────────────────────┐
│ WORLD / OBSERVATORY   Run · Tick · LIVE/REPLAY · controls   │
├──────────────┬───────────────────────────────┬───────────────┤
│ Navigation   │                               │ Inspector     │
│ / Layers     │          World Canvas         │ / Evidence    │
│ collapsible  │                               │ collapsible   │
│              │                               │ resizable     │
├──────────────┴───────────────────────────────┴───────────────┤
│ Timeline / Event Log — collapsible + resizable              │
└──────────────────────────────────────────────────────────────┘
```

The world canvas is the priority surface.

## Collapse-first panel rule

Every persistent support panel must support collapse.

Required:

- left navigation/layer rail can collapse to icons;
- right inspector can collapse completely;
- bottom timeline/event drawer can collapse completely;
- lineage can switch between docked panel and full-canvas view;
- collapsing panels expands the world canvas immediately;
- reopening restores prior panel size when practical;
- panel state is local presentation state.

Do not require the researcher to navigate away from the world to recover screen space.

## Core components

### Top status bar

Show compactly:

- run ID;
- tick/state version;
- live/replay state;
- run status;
- play/pause/step controls where applicable;
- provenance/evidence shortcut.

Avoid marketing copy in the operational shell.

### Agent token

At useful zoom levels show:

- sprite;
- display name;
- optional canonical ID;
- selected state.

At low zoom, progressively reduce labels rather than overcrowd.

### Inspector

Use flat stacked sections with hairline dividers:

- identity;
- lifecycle;
- lineage;
- recent interactions;
- cognition/evidence;
- exact provenance.

Evidence and hashes should be copyable/selectable but visually secondary until expanded.

### Lineage view

Use a readable tree/DAG treatment with sprite thumbnails and canonical IDs.

Do not decorate branches as `strong`, `successful`, or `dominant` without a registered derived analysis.

### Event timeline

Prefer compact rows and filter chips.

Event type should remain recognizable without relying on color alone.

## Sprite presentation

Sprites are content, not UI chrome.

They may be colorful and visually distinct while the surrounding Observatory remains restrained.

Sprite generation semantics live in `SPRITES.md`.

The style target is compact, simple artificial organisms with strong silhouettes and many combinatorial variants. Do not copy existing collectible-creature characters or proprietary body parts.

## Motion

- hover/focus: ~100ms;
- panel open/close: ~200ms;
- committed-event appearance: up to ~300ms;
- no bounce/spring/celebration motion;
- `prefers-reduced-motion` must preserve the complete workflow.

Animations visualize committed facts only.

## States

### Loading

Use fixed-dimension skeletons on `#f9f9fa`. Do not hide already available context while a detail artifact loads.

### Empty

Use concise explanatory copy and a single relevant action.

### Error

State whether the problem is presentation/transport/evidence lookup. Never imply a simulation failure unless canonical evidence says so.

### Disconnected

Show a calm Observatory-disconnected state. The copy should make clear that simulation may continue headlessly.

## Research-grade provenance

Every detailed scientific object should offer a path to its provenance.

For a selected behavior, the UI should make it possible to reach:

```text
run -> tick -> canonical event/action -> evidence ref -> raw generation/context -> experiment identity
```

Provenance is a first-class interaction, not hidden debug chrome.

## Accessibility

- keyboard-accessible collapse/expand controls;
- visible focus state;
- sufficient contrast;
- no information by color alone;
- 40px+ common touch targets where practical;
- responsive layout must preserve world-canvas usability;
- narrow screens may turn side panels into drawers, but they remain dismissible.

## Non-goals

Do not add:

- sci-fi hologram HUD styling;
- decorative neon glows;
- role/personality badges unsupported by canonical/derived evidence;
- game-like health bars for concepts that do not exist;
- permanent panels that steal canvas space;
- UI controls that directly mutate simulation state.
