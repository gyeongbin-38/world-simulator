# SEQ-610 — Replay observation

**Status:** IMPLEMENTED / V1

**Parent:** ARC-600

**Question:** What does the observation cursor mean without changing SEQ-230?

## Cursor contract

The UI explicitly observes **after closing tick N** for N in 0…H−1. World metrics
use the exact committed S_(N+1), including births and deaths committed while
closing N. Evidence shows both the observation tick and snapshot boundary/version.
This is not S_N and is not a new canonical state. Tick H is a separate **Final
boundary** view of the same S_H, with no tick-H action or commit invented.

Birth at N exists after that commit but is **Born · not active** on cursor N;
first_active_tick is N+1. At cursor N+1 a living child is **Active / alive**, meaning
eligible by lifecycle, not proof that cognition happened. Actual attempts are
listed separately. At the final boundary, a child whose first_active_tick is H is
eligible but has no recorded cognition after the horizon.

Natural death while closing N removes the agent from S_(N+1). Display **Dead** in
that post-commit frame, death commit tick N, and effective death boundary N+1.
Do not label a future scheduled lifespan boundary as an observed death. Age is
completed active ticks at the observed boundary, capped at the recorded death
boundary; include the definition in the Inspector. Born/inactive children have
zero completed active ticks. Founders come from S_0, not a synthetic birth event.

## Temporal filtering

Every world/agent/events/lineage query shares the same required bounded cursor.
Before birth the child and its ID, edges, actions and metadata are absent (agent
lookup returns 404). Before death, death fields are null. Proposal state and
messages come from the selected snapshot, never the final current tables.
Attempts and commits are filtered at N; exact evidence is inaccessible before
its first recorded tick. All default lineage contains only existing agents.

Full Run identity, final outcomes and manifests appear only in explicitly labeled
Full Run disclosure. They never supply selected-tick metrics. Timelines default
to history through the cursor and group attempts by tick; no order between peer
attempts is invented. Canonical event ordinals remain inspectable separately.

## Delivery

Seek, play, pause and speed change only browser observation time. Abort stale
requests and publish a frame atomically with its tick. Do not show an old frame
under a newly selected tick. Clear a selected agent if it does not yet exist.
Playback pauses on fetch failure and at H. Left/Right and Space work outside
editable controls. Reduced motion disables presentation transitions.
