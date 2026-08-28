# Documentation & Context Policy

## Goal

Keep repository knowledge discoverable without automatically injecting the entire repository into an LLM context.

## One Fact, One Owner

A meaningful semantic rule should have one owner document.

Other files:
- link to the owner;
- summarize only when necessary for navigation;
- do not create competing definitions.

## File roles

### `AGENTS.md`
Small always-on coding-agent guide.

It contains:
- how to find authority;
- a few catastrophic invariants;
- work/change discipline.

It is not the architecture manual.

### `DESIGN.md`
On-demand compact system map.

It is not the source of exact lifecycle/tick/reproduction semantics.

### `architecture/CONSTITUTION.md`
Foundation invariants.

### `architecture/INDEX.md`
Address book: question/ID → owner document.

### `architecture/views/*.md`
One bounded architectural question per document.

### `docs/observatory/SPRITES.md`
Visual identity only.

### Historical documents
Old Architecture Books, step ZIPs, generated validation reports, and superseded drafts belong outside active retrieval routes.

## Default loading sequence

```text
AGENTS.md
→ current task/path/error
→ architecture/INDEX.md lookup
→ primary owner document
→ additional owner only if boundary crossing requires it
→ code/tests
```

Do not automatically load:
- DESIGN;
- every architecture view;
- every research note;
- historical Architecture Book;
- previous step/foundation ZIP contents.

## Progressive disclosure

Prefer:
1. exact owner by path/task/symbol;
2. exact section/range;
3. related boundary owner;
4. broader repository search;
5. large-context synthesis only when the task genuinely needs it.

Context-window capacity is not a target to fill.

## Duplication allowance

Critical failure-prevention rules may appear as a short reminder in `AGENTS.md`, but detailed mechanics must remain in their owner document.

## Maintenance

Eventually automate:
- broken owner links;
- duplicate IDs;
- orphan views;
- oversized bootstrap docs;
- historical/archive files accidentally routed into normal context;
- stale references;
- architecture view without tests once implementation exists.

Documentation routing is an engineering subsystem and should be evaluated using task success, context size, retrieval accuracy, and regression rate.
