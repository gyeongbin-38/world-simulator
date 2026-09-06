# A-LifeLM Architecture Index

This file is the Markdown architecture address book.

Each active document owns one bounded question. Do not duplicate its detailed rules in other Markdown files.

## Active owner documents

| ID | Owner document | Status | Owns |
|---|---|---|---|
| A00 | `CONSTITUTION.md` | REVIEWED | foundation invariants |
| ARC-000 | `views/ARC-000-system-landscape.md` | REVIEWED | highest-level system boundary and authority path |
| ARC-010 | `views/ARC-010-trust-visibility-boundaries.md` | REVIEWED | authority/information isolation |
| ARC-100 | `views/ARC-100-reference-deployment.md` | REVIEWED | reference physical/runtime deployment roles |
| ARC-200 | `views/ARC-200-simulation-kernel.md` | REVIEWED | kernel component ownership |
| ARC-240 | `views/ARC-240-state-event-protocol.md` | REVIEWED | state/event/artifact/protocol semantics |
| ARC-270 | `views/ARC-270-durable-commit-replay-boundary.md` | REVIEWED | durable commit, evidence, outbox, snapshot, replay boundary |
| ARC-300 | `views/ARC-300-agent-context-fabric.md` | REVIEWED | exact EXP-000 agent-visible ContextPack semantics and hidden information |
| ARC-350 | `views/ARC-350-neural-heredity.md` | REVIEWED | model-independent neural genotype, inheritance law, genetic/cultural firewall, and N0 backend boundary |
| LC-210 | `views/LC-210-agent-lifecycle.md` | REVIEWED | birth activation, maturity, refractory, natural death |
| LC-220 | `views/LC-220-reproduction-proposal-lifecycle.md` | REVIEWED | proposal/accept/reject/conflict resolution |
| SEQ-230 | `views/SEQ-230-one-simulation-tick.md` | REVIEWED | deterministic `S_t → S_(t+1)` causal ordering |
| SEQ-250 | `views/SEQ-250-crash-recovery-resume.md` | REVIEWED | crash recovery, commit ambiguity, and resume semantics |
| SEQ-320 | `views/SEQ-320-exact-context-recall.md` | REVIEWED | EXP-000 recall availability and exact-reference expansion sequence |
| SEQ-351 | `views/SEQ-351-genome-artifact-commit.md` | REVIEWED | N0 genome artifact CAS construction and atomic genome_ref commit ordering |
| DF-260 | `views/DF-260-research-lineage.md` | REVIEWED | raw evidence → dataset → result → claim lineage |
| DF-310 | `views/DF-310-context-compilation.md` | REVIEWED | deterministic ContextPack compilation, provenance, ordering, and hash |
| ARC-600 | `views/ARC-600-observatory-isolation-read-model.md` | IMPLEMENTED / V1 | read-only Observatory authority and source precedence |
| SEQ-610 | `views/SEQ-610-replay-observation.md` | IMPLEMENTED / V1 | observation cursor and replay frame selection |
| ARC-620 | `views/ARC-620-observatory-research-views.md` | IMPLEMENTED / V1 | Observatory views and evidence disclosure |

## Supporting domain documents

| Document | Owns |
|---|---|
| `../docs/DOCS_POLICY.md` | repository documentation/context loading |
| `../docs/observatory/SPRITES.md` | non-causal sprite identity and visual inheritance modes |
| `decisions/ADR-300-001-self-send-addressing.md` | EXP-000 SEND target law and self-addressing prohibition |

## Planned — create only when implementation reaches the gate

Do **not** author these just to make the document count complete.

| ID | Gate / trigger | Question |
|---|---|---|
| ARC-330 | if communication boundary needs expansion | public/directed/private/researcher-only information |
| ARC-400 / WF-410 / SEQ-420 | before controlled interventions/confirmation tooling | experiment control and confirmation workflow |
| ARC-430 | before causal physical space | causal 2D environment |
| ARC-500 / WF-520 | before performance scaling backend | compute admission/batching without causal drift |

## Retrieval rule

A coding task normally loads:
1. `AGENTS.md`;
2. the single primary owner document;
3. additional owner documents only when the task crosses a boundary.

Example:

```text
"proposal acceptance bug"
→ LC-220
→ LC-210 only for lifecycle eligibility
→ SEQ-230 only for same-boundary timing
→ ARC-240 only if state/event/protocol ownership is disputed
```

Never load the archived historical Architecture Book as normal task context.
