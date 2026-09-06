# ARC-620 — Observatory research views

**Status:** IMPLEMENTED / V1

**Parent:** ARC-600

**Question:** How does the Observatory make exact evidence understandable?

Overview, World, Lineage, Timeline and Evidence share one observation cursor.
The main interaction topology uses deterministic SVG positions assigned by stable
run-local identity. Positions do not depend on future births or a running force
simulation. Label the layout as interaction topology, not physical position.
Show recent canonical message/proposal edges only, with explicit edge legends.
Rejected attempts have a separate textual treatment and never a committed edge.

The Inspector exposes canonical identity/copy, lifecycle, completed-active age,
birth/activation/death boundaries, parents and children, recorded attempts with
Law admission, messages, proposal state and exact evidence. Display aliases are
derived presentation metadata only. No inferred motives or personality exist.

Lineage uses two-parent connectors from authenticated birth details, independent
of interaction edges. All agents that have existed by the cursor may appear;
dead agents are labeled. A future child is never displayed in default lineage.

Timeline distinguishes action selection, Law rejection, messages committed,
proposal creation/resolution, births, natural deaths and recorded run completion.
Selecting a row seeks to its tick and focuses its agent when the event association
is recorded. Do not invent a subject where an event's schema lacks one.

Evidence progressively discloses local integrity checks, recorded manifests,
state hashes, selected action scores/probabilities, Gateway intent, grounding
mapping, Law admission and verified raw bytes. The raw text is retained exactly
(large JSON integer precision must survive as source text). The UI's word
"Verified" always names a check actually performed; recorded gates remain labeled
recorded. Complete manifests and final statistics are labeled Full Run.

Use restrained light surfaces, neutral type, limited blue, semantic HTML,
keyboard-operable SVG nodes, visible focus, readable contrast and reduced motion.
There is no causal geography, world-control UI, mutable admin route, or live-run
claim. Loading, missing-source and integrity errors must remain legible.
