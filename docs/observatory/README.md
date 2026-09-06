# Observatory V1

A local, read-only window into the closed EXP-000 pilot. This is observation of
preserved evidence, not a running simulation. There is no model call, tick advance,
proposal acceptance endpoint, database migration, or evidence repair.

## Launch

Requirements: the repository Python environment (Python 3.12+), Node 22.12+ or 24,
and the original preserved archive with its adjacent base and grounding manifests.
No backend dependencies were added. Frontend dependencies are locked with npm.

From the repository root, install and build the frontend:

```powershell
npm --prefix observatory ci
npm --prefix observatory run build
```

Set the evidence path for your machine and start the observation server:

```powershell
$env:WORLD_OBSERVATORY_DATA_ROOT = 'YOUR_PRESERVED_RUN_DIRECTORY'
.\.venv\Scripts\python.exe -m alifelm.observatory
```

Open <http://127.0.0.1:8765/>. A direct observation can be shared locally as
`http://127.0.0.1:8765/?tick=15&view=World`; an optional `agent` parameter is the
canonical agent ID. The URL is presentation state only.

`--data-root`, `--cache-root`, `--static-root`, and `--port` provide explicit
configuration. The default disposable cache is `.observatory-cache/` in this
checkout. Each launch creates a fresh extraction; the archive is never copied
into tracked source. Delete old disposable caches only after closing their readers.
The cache must be outside the preserved source directory.

The API and static build share one loopback origin. For frontend development,
leave the Python server running and run `npm --prefix observatory run dev`; Vite
proxies `/api` to loopback port 8765. Development tooling is not world authority.

## Observation time

For cursor N from 0 through 19, the UI says **After closing tick**: population and
proposal state come from S_(N+1). Cursor 20 is the final S_20 boundary, with no new
action. This convention makes the tick-15 birth inspectable at tick 15 while
showing Child 01 as **Born · not active** until tick 16.

Founders die in the commit closing tick 19, effective at boundary 20. Both fields
appear in the Inspector. Before that commit, no observed death is displayed.
Age means completed active ticks at the observation boundary, capped at recorded
death. Eligibility is separate from recorded cognition: Child 02 is eligible from
tick 20 and has no post-horizon action.

Left/Right step the observation; Space toggles playback outside interactive
controls. The slider, jump field and speed selector change only browser time.
Stale network responses are discarded, errors pause playback, and an old frame
is never displayed with a new tick label.

## Architecture and source precedence

`Canonical SQLite / sealed tick evidence / CAS → Python projection → GET API → React`

The boundary is owned by [ARC-600](../../architecture/views/ARC-600-observatory-isolation-read-model.md).
Time is owned by [SEQ-610](../../architecture/views/SEQ-610-replay-observation.md),
and views by [ARC-620](../../architecture/views/ARC-620-observatory-research-views.md).
Existing LC-210, SEQ-230 and ARC-270 semantics are unchanged.

1. Authenticate the original archive and both manifests using pinned SHA-256.
2. Safely extract into a new cache. Rebind every extracted file's bytes to its
   member in the authenticated archive, including tick records and sidecars.
3. Open SQLite with `mode=ro&immutable=1` and `PRAGMA query_only=ON`. Reject a
   nonempty WAL/journal. The real archive's empty WAL and stale SHM are preserved
   and ignored by immutable SQLite; no checkpoint is attempted.
4. Validate SQLite integrity/foreign keys, all 21 snapshot hashes, the 20-commit
   checkpoint chain, the ordered event suffixes and final materialized tables.
5. Bind every tick's before/after hashes, population, events and artifact refs to
   SQLite. Birth fragment parents are checked against the previously committed
   proposal and resulting child state. Event-to-subject association is verified
   against the existing canonical event-ID hash contract, without running a
   transition or creating an event.
6. Verify all 93 referenced CAS contents and recompute manifest result digests.
   Reconcile final identity, counts, lineage, population history and action
   sequences. Any mismatch withholds normal projection as **Integrity Conflict**.

SQLite owns durable world truth. Sealed tick evidence supplies recorded attempts,
selector scores, Gateway/Law results, grounding mappings and parent details
missing from AgentState. Manifests supply recorded completion/results. No source
silently overrides another when they disagree.

The prior `origin/o0-observatory-foundation` was inspected read-only for isolation,
frame identity and exact-reference ideas. It was not merged or cherry-picked.

## API

All routes accept GET/HEAD; OPTIONS advertises these methods. POST/PUT/PATCH/DELETE
return 405 with no effects. The server rejects non-loopback Host headers and does
not enable cross-origin access. It is a local research viewer, not an Internet
deployment or multi-user authenticated service.

| Route below `/api` | Meaning |
|---|---|
| `/runs` | Discovered supported run summaries; empty when unconfigured |
| `/runs/{run_id}` | Run identity and observation horizon |
| `/runs/{run_id}/ticks/{tick}` | Atomic selected-tick frame |
| `/runs/{run_id}/overview?tick=N` | The same selected-tick frame |
| `/runs/{run_id}/agents/{id}?tick=N` | Agent and its bounded related records |
| `/runs/{run_id}/events?tick=N&category=birth` | Bounded feed; optional category |
| `/runs/{run_id}/lineage?tick=N` | Existing agents and canonical two-parent births |
| `/runs/{run_id}/integrity` | Explicit **Full Run** verification and recorded status |
| `/runs/{run_id}/evidence/{sha256}?tick=N` | Registered exact raw reference |

Manifests or intentional full-run raw reads require `scope=full-run`. Default raw
reads cannot resolve future evidence. A strict digest registry replaces arbitrary
filesystem paths. Raw JSON is returned as source text: the original 256-bit
selector integers survive JavaScript without rounding. `/health` reports reader
availability. No API provides mutation, inference or repair operations.

Read models include `AgentObservation`, `EventObservation`,
`ActionAttemptObservation`, `TickObservation`, run summaries, message/proposal
records, canonical birth/death lineage, integrity and raw evidence responses.
Frames are defensive copies; altering a returned projection cannot change the
reader's next response or any source.

## Frontend

React + strict TypeScript + Vite; plain CSS tokens, no UI kit or state-management
library. Plain SVG renders stable identity slots and two-parent connectors.
This avoids a force-simulation dependency and gives deterministic replay and
keyboard-operable nodes. Glyphs are neutral, presentation-only identity marks;
they encode no scientific trait or geography.

- Overview: selected population, generation depth, births/deaths, topology and feed.
- World: expanded recent topology; message edges come only from committed messages.
  Pending proposals use a separate dashed line. Rejections are textual callouts.
- Inspector: canonical ID/copy, lifecycle, defined age, family, attempts, messages,
  proposal state and verified evidence. Dead founders remain inspectable.
- Timeline: tick groups, type filter and search; selecting an event seeks its tick
  and focuses its recorded subject. Attempts are distinct from canonical records.
- Lineage: selected-tick genealogy with both parents and lifecycle labels.
- Replay: previous/play/pause/next, slider, jump, speed, keyboard and addressable URL.
- Evidence: exact boundary, selector scores/probabilities, Gateway, Law, grounding,
  CAS and source text; Full Run integrity separates locally performed checks from
  recorded G0–G4 results. Final statistics are explicitly labeled Full Run.

React components are in `observatory/src/components/`; `App.tsx` owns the cursor
and abortable frame loading. Layout and details styling are split into two CSS
files. All evidence text is escaped by React; no `dangerouslySetInnerHTML` exists.
Semantic controls, visible focus, native dialog focus/escape, clipboard feedback
and reduced-motion support are included.

## Verification

```powershell
$env:WORLD_OBSERVATORY_DATA_ROOT = 'YOUR_PRESERVED_RUN_DIRECTORY'
.\.venv\Scripts\python.exe -m pytest tests/observatory tests/test_docs_lint.py tests/test_context_router.py -q
npm --prefix observatory run build
# Keep the real observation server running on port 8765:
npm --prefix observatory test
```

Browser tests use the installed Edge on Windows. On other platforms install the
Playwright Chromium browser (`npx playwright install chromium` from `observatory`).
`OBSERVATORY_BROWSER_CHANNEL` and `PLAYWRIGHT_BASE_URL` override the browser and
server. No browser downloads are needed when an appropriate browser is installed.

Backend real-evidence tests explicitly skip if no data root is configured; they
never substitute invented evidence. A release validation must run with the actual
preserved source and zero skipped Observatory tests. Isolated loading/empty/error
browser tests intercept responses; the real-data suite and screenshots do not.

Test results and real-data screenshots are disposable, gitignored artifacts in
`.observatory-cache/validation/` and `.observatory-cache/screenshots/`. Playwright
failure traces are in `observatory/test-results/`.

GPU inference, EXP-000, and P2 scientific runners are not executed: the closed
experiment is the input, not a workload to rerun. Existing deterministic contract
tests may be run to confirm that the additive reader leaves the core untouched.

## V1 limits

One pinned sealed EXP-000 archive/schema is supported. No live subscription,
multi-run selector, physical map, image export service, dark theme or remote
authentication is provided. World edges show a labeled three-tick window;
complete selected history remains available in Timeline and Inspector. Large
future experiments would need pagination and a new layout design. The current
pilot remains bounded to 20 ticks and five recorded agent identities.
