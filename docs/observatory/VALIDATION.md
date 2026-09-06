# Observatory V1 implementation and validation

## Delivery identity

| Item | Value |
|---|---|
| Repository | `E:\WORLD\A-LifeLM_MD_CANONICAL_v1` |
| Branch | `observatory-ui-v1` |
| Closure base / initial HEAD | `2724025776e554528a038cbdc57078d3b9c0bb1c` |
| Origin | `https://github.com/gyeongbin-38/world-simulator.git` |
| Permitted push | `HEAD:refs/heads/observatory-ui-v1` on `origin` |
| Scientific core changed | No |
| Merge performed | No |

The working tree was clean at startup. The branch, origin, base ancestry and
remote branch were checked. This document is part of the delivery commit; its
exact commit SHA and confirmed remote push are reported in the final delivery
message, avoiding a self-referential commit hash inside that commit.

## Evidence and read-only proof

The actual input was the preserved directory
`E:\WORLD\RECOVERY\EXP000_LIVE_GROUNDING_PILOT_V1_R1_20260906`.
This path is supplied through configuration; it is not embedded in production code.

| Identity | SHA-256 |
|---|---|
| Canonical `.tar.gz` archive | `dc7f904957a90be998df603b78c993b5ebdb55ccdd4d0aa20949dca80a9df227` |
| Base manifest | `aa70c88392f52a018af2ea87f096360e0bfd362cb795668e0216215e57490320` |
| Grounding manifest | `1cb4f18c2a4239f73d00c8065353a7f835b5d32abc446e29b70b24d3ecb4e281` |

All three matched before implementation and after verification. The original
archive and manifests were not changed. Actual evidence, generated screenshots,
browser traces and validation artifacts are excluded from Git.

The reader validates all extracted bytes against the authenticated archive,
SQLite integrity and foreign keys, 21 canonical snapshot hashes, 20 committed
boundaries, final materialized tables, ordered event records, sealed tick
before/after identities, two-parent birth details, 93 referenced CAS artifacts,
both recomputed result digests, and manifest trajectory consistency.

Recorded base status is `LIVE_PILOT_COMPLETE`; recorded grounding status is
`LIVE_GROUNDING_PILOT_COMPLETE`. Recorded G0–G4 values are all true. The base result
digest is `9b8d4f63a3ae3311e6a3893928f3a971b3cfb6af20c80413f66cfbe0953af4d7`, and the
grounding result digest is `e8dca7b47bb4239ec3210a6f0fbbb7a9bfe376a440634f3307e05fa9b95966b5`.
The UI labels recorded gates separately from local byte/consistency checks.

SQLite is opened through a dedicated `mode=ro&immutable=1` connection with
`query_only=ON`. Six real write tests attempt INSERT, UPDATE and DELETE, both
with and without `query_only`. All fail with SQLite's readonly error; database
and sidecar bytes remain unchanged. The sealed zero-byte WAL and stale SHM are
preserved. A nonempty WAL/journal is rejected instead of silently ignored.

Sixteen representative HTTP mutation requests (four methods × four routes)
return 405 with `Allow: GET, HEAD, OPTIONS` and unchanged observations. Digest
validation, temporal evidence access, traversal, missing evidence, cache
tampering and a non-loopback Host are tested. Replay network requests are GET
only. No scientific runner, GPU inference, model retry or simulation commit runs.

## Architecture and implemented behavior

The data flow is canonical persistence/evidence → independent Python read models
→ loopback GET API → React. The frontend never reads SQLite. Source precedence,
the exact endpoint table, read models, components, commands and limitations are
documented in the [operator and architecture guide](README.md).

SQLite owns durable world state. Sealed tick records supply attempts, scores,
Gateway/Law results and additional birth/grounding evidence, bound to SQLite.
Manifests supply recorded run identities and final results. CAS supplies exact
raw bytes. Disagreement produces Integrity Conflict; no source is guessed or
repaired. Raw selector integers remain original source text in the browser.

Overview, expanded World, Inspector, Timeline, Lineage, Replay and Evidence are
implemented and integrated. Plain SVG supplies stable interaction slots and
two-parent lineage. No force simulation or graph library is needed for five
agents. The topology is explicitly non-spatial. Display aliases and glyphs are
presentation only. The light shell uses system fonts, neutral surfaces, restrained
blue links, open metrics and progressive evidence disclosure.

Cursor N means after closing tick N and reads S_(N+1); cursor 20 is the final
S_20 boundary. All selected-tick data shares this cursor. Future children and
their identities are absent, death fields are hidden until the death commit,
proposal states come from the selected snapshot, and future raw references are
inaccessible by default. Full Run disclosures are explicit. Aborted/stale
requests cannot replace a newer observation.

## Exact semantic assertions

| Recorded fact | Verified result |
|---|---|
| Founders / final population | 3 / 2 |
| Births / natural deaths / birth conflicts | 2 / 3 / 0 |
| Maximum generation depth | 1 |
| Selected WAIT / SEND / PROPOSE / ACCEPT / REJECT | 35 / 16 / 8 / 5 / 0 |
| Committed messages / proposals created | 9 / 8 |
| Child 01 birth / first active tick | 15 / 16 |
| Child 01 at tick 16 | SEND attempted to self, rejected by Law; no message edge or committed message |
| Child 01 at ticks 17 / 18 / 19 | Admitted PROPOSE / admitted PROPOSE / admitted WAIT |
| Child 01 parents | Founder C and Founder B, exact canonical IDs |
| Child 02 birth / first active tick | 19 / 20 |
| Child 02 post-horizon action | None; none invented |

Action selection is never equated with a canonical outcome: 16 SEND selections
produce nine committed messages, and five ACCEPT selections produce two births.

## Automated validation

The complete final Python selection passed **213 tests, zero failed, zero skipped**
in 64.44 seconds: 85 Observatory safety/real-evidence tests, 17 documentation/router
tests, and 111 existing domain/persistence/kernel/context contract tests.
JUnit output: `.observatory-cache/validation/backend.xml`.

The raw-integer test was subsequently refined to read the expected integer from
the actual source rather than embed its real evidence value in Git. Its focused
rerun passed: **1 passed** in 13.13 seconds.

Strict TypeScript checking and the Vite production build passed. Final initial
assets total approximately 27.44 kB CSS and 230.67 kB JS before gzip (6.60 kB and
71.19 kB gzip). There are no external fonts or image downloads at runtime.

The full real-browser suite passed **17 tests, zero failed, zero skipped, zero
retries** in 552.93 seconds: 14 frontend behavior tests, one complete real-evidence
E2E sequence, and two visual capture scenarios. Full-suite JSON:
`.observatory-cache/validation/frontend-full-suite.json`.

After the final contrast polish and source-integer assertion refinement, the
focused browser rerun passed **4 tests, zero failed, zero skipped** in 156.88
seconds: rejected SEND/raw precision, the full real-evidence E2E flow, and both
visual capture scenarios. Final rerun JSON is
`.observatory-cache/validation/frontend-results.json`. All ten final screenshots
were opened and visually reviewed; no horizontal overflow or first-child/replay
dock overlap was found at either target size. Long Inspector and Evidence content
remains scrollable beneath the persistent observation controls.

The E2E sequence loads real evidence → tick 15 birth → Child 01 Inspector → exact
parents/birth/activation → tick 16 rejected SEND with no message → tick 17 admitted
PROPOSE → two-parent Lineage → exact archive/result identities in Evidence.
It records zero page or application console errors.

The browser tests also cover loading/empty/error, metrics, replay and speed,
keyboard, copy-to-clipboard, future child hiding, Timeline type/search filters,
event seeking, terminal Child 02, raw evidence, delayed response ordering, fetch
failure and reduced motion. Visual tests assert the first child remains above
the replay dock at both desktop and laptop sizes.

An initial shared Playwright download failed on its global cache lock. Installed
Microsoft Edge was used with isolated test profiles. An initial 45-second page
setup limit was insufficient on the loaded workstation; the harness timeout is
90 seconds, with retries still disabled. These are browser tooling adjustments,
not changes to the experiment or its failure semantics.

GPU/model integration, EXP-000/P2 runners, and new scientific experiments were
intentionally not run: the input experiment is closed and its scientific behavior
must remain unchanged. Existing deterministic core regressions passed instead.

## Visual inspection and polish

A real browser was launched. `agent-browser` navigation, interactive snapshot,
screenshot and content/overlay checks were performed. A Paseo browser also loaded
the real first-birth view with zero console errors. Playwright captured actual
evidence at **1440×1050** and **1280×900**. All five required views are captured at
each size under `.observatory-cache/screenshots/1440/` and `/1280/`:

| File | Contents |
|---|---|
| `01-overview.png` | Real tick-17 overview and committed/pending interactions |
| `02-first-birth.png` | Tick-15 first birth; newborn is not active |
| `03-child-inspector.png` | Child 01 identity, lifecycle and parents |
| `04-lineage.png` | Both canonical parents connected to Child 01 |
| `05-evidence.png` | Selected-tick evidence and Full Run integrity disclosure |

Initial screenshots exposed excessive vertical space that put lower nodes near
the floating replay dock, and an edge passing behind an agent label. Polish
reduced graph height and header spacing, adjusted stable SVG slots, added a
short-viewport layout, gave text an opaque legibility stroke, and increased small
metadata/lifecycle contrast. The World view remains dominant, hashes remain
behind disclosure, rejected attempts have a distinct textual callout, and the
timeline stays a readable activity feed. No neon, geography or world controls
were introduced.

## Dependencies and changed scope

Runtime additions: React and React DOM 19.2.8 for the interface. Development:
TypeScript 7.0.2, Vite 8.2.2, Playwright 1.63.0 and Node/React type declarations.
The npm lockfile is committed. Python remains standard-library-only beyond the
existing repository. Prettier was used as a development command, not added as a
runtime dependency. No graph library, full-stack framework, UI kit, Redux,
database server or AI SDK was added.

New implementation files:

- `src/alifelm/observatory/{__init__,__main__,evidence,models,projection,server}.py`
- `observatory/src/{App,main}.tsx`, `types.ts`, `styles.css`, `details.css`
- `observatory/src/components/{Shared,Graphs,Inspector,Timeline,Replay,Evidence}.tsx`
- `observatory/{index.html,package.json,package-lock.json,tsconfig.json,vite.config.ts,playwright.config.ts}`
- `observatory/public/observatory.svg`
- `observatory/e2e/{frontend,real-run}.spec.ts`
- `tests/observatory/{conftest,test_safety,test_projection}.py`
- Three Observatory owner documents in `architecture/views/`
- `docs/observatory/{README,VALIDATION}.md`

Existing changes: `.gitignore`, architecture index registration, and the
documentation linter plus its regression test. The linter now prunes dependency,
build and disposable evidence directories before traversal. Index wording keeps
the existing minimal lifecycle/context routes unchanged.

Protected `domain`, `kernel`, `context`, `model`, `live`, `persistence` and
scientific runner files have no diff against the closure base. No lifecycle,
LawValidator, selector, grounding, context-construction, or experiment code was
modified. Owner documents/tests changed are limited to the Observatory owners,
the new observation tests and the documentation-lint regression test.

V1 is deliberately limited to this pinned archive/schema, local sealed replay,
light mode and the small deterministic SVG layout. Live streaming, large-run
pagination, remote authentication and multi-run operation are future work.
