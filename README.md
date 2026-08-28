# A-LifeLM

A-LifeLM is an instrumented artificial-life research platform for observing how minimally socially constrained language-model agents communicate, choose partners, form persistent interaction patterns, reproduce, transmit information across generations, and respond to controlled experimental interventions.

This repository is **not a game architecture**. A graphical Observatory may look game-like, but simulation truth, experimental law, and research evidence remain outside the UI.

## Start

Humans:
1. read `DESIGN.md`;
2. use `architecture/INDEX.md` to find the owner document for a question;
3. read only the relevant bounded document.

Coding agents:
1. read `AGENTS.md`;
2. route the task through the architecture index/context router;
3. load only the required owner documents.

Do not preload every Markdown file.

## Current state

- Foundation architecture: **REVIEWED**
- Current implementation target: deterministic EXP-000 kernel
- Real LLM integration: **after deterministic/fault/replay validation**
- Observatory: later, read-only
- Neural heredity: later experimental gate

## Documentation rule

One fact has one semantic owner.

```text
AGENTS.md          = how an agent works in the repo
DESIGN.md          = compact system map
CONSTITUTION.md    = non-negotiable foundation invariants
architecture view = one bounded architectural question
DOCS_POLICY.md     = documentation/context-loading policy
SPRITES.md         = Observatory visual identity only
tests              = executable proof, once implementation exists
```

If two documents appear to define the same rule, `architecture/INDEX.md` identifies the owner. Non-owner documents should link rather than redefine it.
