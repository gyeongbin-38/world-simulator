# AGENTS.md — A-LifeLM

A-LifeLM is a scientific artificial-life research platform. Treat correctness, causal isolation, reproducibility, and research validity as higher priority than convenience or visual polish.

## 1. Do not preload the repository

Never automatically read every `.md`, architecture document, historical draft, log, or generated artifact.

Start with this file only.

Then:
1. identify the task/path/symbol;
2. consult `architecture/INDEX.md` or the context router;
3. load the smallest set of owner documents required;
4. expand only if the current evidence is insufficient.

`DESIGN.md` is on-demand, not mandatory startup context.

## 2. Source-of-truth order

For Markdown-only architecture work:

1. `architecture/CONSTITUTION.md`
2. owner document registered in `architecture/INDEX.md`
3. tests/implementation evidence when available
4. `DESIGN.md`
5. `README.md`

Later machine-readable specs may become the exact field/schema authority, while these Markdown views retain semantic ownership and rationale.

## 3. Critical invariants

- Model output is a proposal, never a direct canonical-state write.
- Canonical state changes occur only through the validated commit boundary.
- Tick causality never depends on inference completion time, wall time, batch position, or thread order.
- Same-tick peer model outputs are not visible to one another in EXP-000.
- Newborns committed at tick `t` first participate at tick `t+1`.
- EXP-000 has no central mate score, assigned social role/personality, causal physical space, resource economy, synthetic affect, or neural heredity.
- Infrastructure failures are not agent deaths.
- Hardware capacity censors/stops a run; it must not silently become reproductive selection.
- Analysis and Observatory are non-authoritative.
- Hidden lineage/internal seeds/research labels are not agent-visible by default.
- Confirmatory claims require fresh confirmatory runs rather than reuse of discovery data.

## 4. Task routing

Use `architecture/INDEX.md`.

Examples:
- lifecycle / lifespan / birth / death → `LC-210`
- proposal / accept / reject / reproduction resolution → `LC-220`
- tick order / same-tick visibility / batching causality → `SEQ-230`
- state vs event vs protocol → `ARC-240`
- kernel ownership → `ARC-200`
- trust / visibility / authority boundaries → `ARC-010`
- research dataset / claim lineage → `DF-260`
- sprite/visual identity → `docs/observatory/SPRITES.md`

Do not copy routing tables into additional files.

## 5. Architecture-change trigger

Do not treat these as ordinary code edits:
- changing tick visibility/timing;
- changing birth/death timing;
- changing agent-visible information;
- changing reproduction eligibility/resolution;
- changing canonical ownership;
- changing replay/evidence semantics;
- making visualization causal.

Such work requires updating the owning architecture document first.

## 6. Implementation order

Current direction:

```text
deterministic domain types
→ deterministic fake ModelRuntime
→ in-memory barrier tick
→ communication / reproduction / lifecycle
→ in-memory commit
→ executable foundation tests
→ durable persistence / replay design
→ persistence implementation
→ real model backend
→ repeated headless EXP-000
→ analysis
→ Observatory
```

Do not start with the UI or a real LLM.

## 7. Completion rule

Before finishing implementation work:
- run the smallest relevant tests;
- verify the owning architecture rule;
- avoid unrelated documentation rewrites;
- report which owner documents/tests changed.
