# ARC-600 — Observatory isolation and read model

**Status:** IMPLEMENTED / V1

**Parents:** ARC-240, ARC-270, DF-260

**Question:** How can a browser observe sealed EXP-000 evidence without gaining simulation authority?

## Boundary

Canonical persistence → read-only projection → GET API → browser.

V1 reads the closed pilot only. It never constructs a simulation runner, a model
runtime, a writable persistence adapter, or a CAS writer. No inference, migration,
repair, simulation retry, or commit occurs. Kernel, domain, context, model, live,
and persistence implementations are protected and unchanged. Pure existing
snapshot deserialization/hash validation may be reused; writable store
constructors and replay adapters must not be used.

## Source precedence

1. Pinned archive and manifest SHA-256 identities authenticate the preserved input.
2. SQLite materialized state and its committed snapshot/hash chain own world facts.
   Validate current tables, commit metadata, ordered event suffixes, and artifacts.
3. Sealed tick records supply attempts, scores, Gateway/Law results and transition
   details (notably two-parent birth identity, absent from AgentState). Bind them
   to the corresponding SQLite before/after hashes, event identities and snapshot
   changes before using them. No fragment creates a canonical event by itself.
4. Manifests own recorded run status and result identity. Recompute their digests
   and reconcile trajectory counts/records with SQLite and tick records.
5. CAS owns referenced raw bytes, checked against each digest on read.

Any disagreement is an **Integrity Conflict**; withhold the normal world view.
Missing or corrupt required input is an evidence error, never an invitation to
repair or rerun. Recorded gate status is distinct from local validation results.

## Input and transport

Configure `WORLD_OBSERVATORY_DATA_ROOT` or `--data-root`; no machine path is baked
into code. Hash before extracting. Extraction uses a new disposable cache, never
the evidence source. Reject traversal, Windows drive/ADS names, absolute paths,
case-insensitive duplicates, links, special files and oversized archives.
Never put actual evidence in Git. Open SQLite with `mode=ro&immutable=1` plus
`query_only=ON`; this adapter accepts only sealed, checkpointed SQLite archives
with no nonempty WAL/journal. The sealed pilot includes a zero-byte WAL and stale
SHM index; immutable mode ignores both without rewriting them. It never opens a
live database.

The local server binds 127.0.0.1. World APIs allow GET/HEAD/OPTIONS only; mutation
methods fail with 405 and no effects. Exact digest lookup uses a bounded registry,
never user-provided filesystem paths. Evidence references carry an earliest tick;
full-run manifests require an explicit Full Run request. Browser data is untrusted
text, not executable HTML. UI positions, aliases and replay state are local only.

## Verification

Safety, semantic projection, corruption, temporal filtering and HTTP tests live
in `tests/observatory`. Browser interaction tests live in `observatory/e2e`.
The historical `origin/o0-observatory-foundation` documents were read for isolation,
identity and exact-reference ideas; no branch was merged. V1 uses compact top
navigation and sealed replay instead of O0's speculative live/dockable panels.
