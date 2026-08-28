# ARC-300 — Agent Context Fabric

**Status:** REVIEWED  
**Parent:** ARC-200  
**Freeze state:** IMPLEMENTATION-READY  
**Question:** What exact information may reach one agent during one cognition opportunity, and what must remain inaccessible?

## Principle and scope

> Context is an experimental treatment, not a dump of canonical state.

EXP-000 exposes the minimum information required to address another active
agent, exchange directed text, use the bilateral new-agent protocol, or take no
primary action. Availability in canonical state, persistence, analysis, or UI
does not imply model visibility.

This view owns agent-visible ContextPack semantics. DF-310 owns compilation and
provenance. SEQ-320 owns the recall decision. Exact model-facing action labels
and descriptions have one field-level owner: the versioned
`action-presentation` machine contract registered under this view.

The I-02 `CognitionFixture` remains a fake-runtime test fixture and is not an
ARC-300 ContextPack or a source of Context Fabric semantics.

## EXP-000 visibility baseline

| Candidate | Baseline decision | Model-visible projection |
|---|---|---|
| Own opaque agent ID | VISIBLE | The opaque ID only. No embedded lineage, generation, role, or model identity. |
| Current simulation tick | HIDDEN | Tick remains a compiler/evidence binding. It is not rendered in EXP-000. |
| Own age | VISIBLE | Non-negative active age computed from the bound `S_t`; no birth tick, first-active tick, lifespan, or death threshold. |
| Active-agent directory | VISIBLE | Opaque IDs of other agents active in `S_t`, with no profile, rank, age, lineage, location, or analysis label. |
| Directed messages delivered to self | VISIBLE | Sender opaque ID and exact delivered body, beginning only at the committed availability boundary. |
| Own sent messages | BOUNDED HISTORY | Exact committed body and recipient, subject to the personal-history policy. |
| Pending proposals addressed to self | VISIBLE PROTOCOL | Exact proposal identity and proposer opaque ID only after LC-220 visibility permits it. |
| Own outgoing proposals | VISIBLE PROTOCOL | Exact proposal identity, target opaque ID, and currently committed public state. |
| Resolution of own proposals/actions | VISIBLE WHEN COMMITTED | A neutral projection of a committed outcome involving self. No successful state is invented from an uncommitted or failed action. |
| Personal interaction history | BOUNDED HISTORY | Exact committed projections that self was entitled to observe, selected by DF-310. |
| Neutral action mechanics | VISIBLE | Version-pinned affordances sufficient to produce a valid action without recommending an action. |

The peer directory excludes self because own identity has a separate projection.
The directory describes current addressability only; it is not evidence of a
relationship.

## Agent-hidden baseline

The ContextPack model-facing region must not contain:

- exact `natural_death_tick`, the global lifespan threshold, birth tick, or
  first-active tick;
- parent IDs, child relationships, lineage, generation, or `agent_birth_seq`;
- causal random seeds or seed derivation material;
- model/checkpoint/provider digest or runtime placement;
- another agent's directed messages, private interaction history, raw model
  output, or unshared action outcome;
- uncommitted ActionIntents, ValidatedIntents, transition fragments, birth
  candidates, or same-tick peer outputs;
- global transcript or global event stream;
- researcher notes, interventions not visible through an explicit channel,
  exploratory labels, centrality/community measures, or social interpretations;
- future genome, adapter, neural-heredity, resource, affect, or private
  modulation state;
- Observatory sprite identity, appearance, position, animation, or UI state.

The model may infer hypotheses from information it legitimately observes. Such
inference does not authorize the compiler to provide the hidden source facts.

## ContextPack authority and structure

A finalized `ContextPack` is an immutable, versioned ARTIFACT/evidence value.
Compiler work before finalization is PROTOCOL. Neither form is mutable
`AgentState`, model memory, or a competing canonical authority.

The machine contract separates:

| Region | Purpose | Rendered to model? |
|---|---|---|
| Stable prefix reference | Versioned neutral mechanics and action-presentation reference | Yes, after model-specific rendering |
| Current self projection | Own opaque ID and own age | Yes |
| Visible peer directory | Active peer opaque IDs in neutral deterministic order | Yes |
| Newly delivered information | Exact directed records first available at this boundary | Yes |
| Visible protocol state | Incoming/outgoing proposal projections and visible committed outcomes | Yes |
| Prior personal-visible history | Exact bounded records selected under the frozen history policy | Yes |
| Provenance and ArtifactRefs | Exact sources for every included item | No |
| Snapshot/policy/order binding | Run, opportunity, `S_t`, and policy identities used to compile | No |
| Generation/runtime binding | Model profile, generation policy, and seed identities used after compilation | No |
| Research telemetry | Category counts and later tokenizer/cache measurements | No |

Model-specific rendering must consume only the model-facing region plus the
referenced stable action presentation. It may not render infrastructure or
research telemetry accidentally.

## Stable prefix and action presentation

The stable prefix contains only invariant mechanics needed to interpret the
ContextPack and submit one primary action. It contains no role, personality,
mate preference, survival goal, cooperation goal, civilization goal, reward,
or preferred action frequency.

Internal canonical actions remain `SEND`, `PROPOSE`, `ACCEPT`, `REJECT`, and
`WAIT`. Their exact model-facing labels and descriptions exist only in the
`action-presentation` machine contract. Other owner documents reference its
policy ID and version and must not copy the labels.

The model-facing output contains only the selected neutral action label and its
payload. The Cognition Gateway binds the opportunity's intent identity, actor
identity, and hidden tick and parses that selection into the internal
`ActionIntent`. The model is not shown a hidden field merely so it can echo it.

Changing wording, examples, labels, output grammar, or action ordering changes
the action-presentation version and therefore the experimental treatment and
ContextPack identity.

## No mutable semantic memory

EXP-000 has no model-written diary, hidden journal, semantic self-summary,
autonomous memory mutation, vector memory, or global cultural board. The model
cannot write arbitrary text into future context except through a committed
domain action visible under the same rules as any other agent action.

Personal history is regenerated from committed State/Event/Artifact sources the
agent was entitled to observe. It is not copied between processes or inherited
by offspring. A newborn's first ContextPack contains no parent transcript,
private history, lineage-derived record, or pre-birth personal experience.

## Bounded history baseline

Current mechanics, newly delivered records, and currently visible pending
protocol state are mandatory categories and are not displaced by prior history.
Prior personal-visible history is bounded by a non-negative semantic record
limit pinned in `ContextPolicy`; no universal tokenizer-size budget is declared
by this architecture.

The run/experiment manifest must freeze that limit before execution. DF-310
owns exact selection and ordering. EXP-000 performs no lossy summarization.
Changing the limit or selection rule changes context identity and condition
metadata.

## Same-tick isolation

Every tick-`t` ContextPack binds to the same immutable `S_t` and only committed
evidence visible at that boundary:

```text
agent A tick-t output
        -X-> agent B tick-t ContextPack
```

All packs are compiled or logically bound in P3 before P4 model execution can
introduce completion order. Inference, thread, batch, storage, or cache order
cannot add, remove, or reorder model-visible content.

## Pretrained-language limitations

Neutral presentation reduces imposed framing but cannot erase pretrained model
priors. Opaque IDs, words describing directed text and bilateral creation, age,
and agent-authored message bodies may still activate learned social concepts.
The model may also infer temporal or relational patterns from legitimate
observations.

These are documented limitations. They are not corrected by adding stronger
social instructions, hidden labels, or researcher interpretation. Wording and
model profile remain versioned treatment metadata for later comparison. The v1
fixed action-presentation order may itself create a positional prior; it is
pinned and recorded rather than claimed to be bias-free. A rotated or otherwise
changed action order is a separate treatment version.

## Owner boundaries

- ARC-010 owns the trust boundary; this view freezes its exact EXP-000 agent projection.
- ARC-200 and SEQ-230 retain kernel phase and same-snapshot authority.
- ARC-240 retains State/Event/Artifact/Protocol classification.
- LC-210 retains activation and age facts; this view exposes only the age projection.
- LC-220 retains proposal states and visibility timing.
- DF-260 retains research lineage; DF-310 defines ContextPack source provenance.
- ARC-270 retains durability rules for finalized ContextPack artifacts.
- SEQ-320 owns exact-recall availability and sequence.
