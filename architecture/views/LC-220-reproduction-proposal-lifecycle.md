# LC-220 — Reproduction Proposal Lifecycle

**Status:** REVIEWED  
**Parent:** ARC-200  
**Question:** How does agent-selected bilateral reproduction resolve without central mate selection or hidden social assumptions?

## Core rule

The platform never chooses a mate for an agent.

A child may be created only from:
1. an agent-originated proposal;
2. a matching explicit target acceptance;
3. deterministic lifecycle/protocol eligibility;
4. successful same-boundary conflict resolution;
5. one authoritative commit.

## Proposal lifecycle

Canonical proposal states:

```text
NONEXISTENT
   ↓ valid PROPOSE committed
PENDING
   ├─ valid REJECT committed ─────────→ REJECTED
   ├─ valid ACCEPT + successful birth → ACCEPTED
   ├─ expiry rule if enabled ─────────→ EXPIRED
   └─ impossible/invalidated relation → INVALIDATED
```

`ACCEPTED`, `REJECTED`, `EXPIRED`, and `INVALIDATED` are terminal for that proposal.

An acceptance intent is not itself an immediate proposal-state mutation. It first becomes a birth candidate. If the birth candidate loses deterministic conflict resolution, that acceptance is not committed as a successful acceptance and the proposal remains PENDING unless another boundary rule expires/invalidates it.

## Creation and visibility

A proposal committed while closing tick `t`:
- has `created_tick = t`;
- becomes target-visible no earlier than `S_(t+1)`;
- cannot be accepted or rejected by target cognition during tick `t`.

## Eligibility

Proposal/acceptance processing may require only experiment-law constraints such as:
- involved agents exist and are alive/active in the validating snapshot;
- required maturity has been reached;
- required refractory interval has ended;
- target/proposal identity is valid;
- proposer is not targeting self;
- acceptance/rejection names the exact proposal.

Forbidden EXP-000 selection criteria:
- fitness/breed score;
- tournament selection;
- role;
- family label;
- mood/affect/hormone;
- researcher compatibility;
- genetic superiority/distance preference;
- forced reproduction.

## Multiple simultaneous proposals

EXP-000 does not impose monogamy/exclusivity by limiting each agent to one pending proposal.

An agent may participate in multiple pending proposals.

Protocol idempotency may deduplicate exact repeated transport/intent identity, but must not create a social preference.

## Same-boundary birth conflict

An agent may participate in at most one successful birth per commit boundary.

If multiple otherwise-valid birth candidates share any parent in the same boundary:

```text
reject all conflicting birth candidates
reason = MULTI_BIRTH_BOUNDARY_CONFLICT
```

Do not choose a winner using:
- stable ID order;
- inference completion order;
- random mate ranking;
- proposal age;
- researcher score.

Conflicted proposals remain PENDING unless a separate expiry/invalidation rule also applies at that boundary.

## Expiry

EXP-000 does not require an arbitrary proposal TTL.

Baseline may use no expiry (`expires_at_tick = null`), relying on explicit rejection, successful acceptance, or invalidation when a participant can no longer participate.

If a future condition enables TTL, it must be uniform/manifest-pinned and treated as an experimental law.

A target acceptance performed in tick `t` is evaluated from `S_t`. If an expiry becomes effective only at `t+1`, the valid tick-`t` acceptance is resolved before expiry.

## Participant death

If a proposal remains unresolved and a participant is absent/dead in the next canonical boundary, the proposal becomes INVALIDATED.

However, a valid acceptance and successful birth generated from `S_t` may still commit even if a parent naturally dies at the same `t → t+1` boundary.

## Child initialization

Successful birth:
- creates a fresh opaque child identity;
- records researcher-visible parent lineage;
- copies no parent transcript/private history;
- uses the same baseline model origin/config in EXP-000;
- uses NullGenome semantics in EXP-000;
- assigns independent deterministic generation/randomness identity;
- activates the child at `t+1`.

## Refractory consequence

Refractory is applied only after a successful birth, not for proposal creation, rejection, failed validation, or multi-birth conflict.
