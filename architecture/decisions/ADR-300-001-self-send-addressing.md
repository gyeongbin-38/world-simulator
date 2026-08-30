# ADR-300-001 — Self-SEND Addressing

**Status:** ACCEPTED  
**Date:** 2026-08-30  
**Decision scope:** EXP-000 baseline architecture gap  
**Change class:** C2 domain-contract clarification

## Context

ARC-300 exposes the actor's own opaque identity separately and excludes that
identity from the active-peer directory. The model-facing SEND affordance says
that its target is one listed opaque agent identity. The historical law
validator nevertheless accepted a SEND whose `target_agent_id` equaled the
actor, leaving an invisible addressing affordance and no frozen canonical law.

## Decision

`SELF_SEND = FORBIDDEN`.

A domain-valid SEND requires an active target distinct from the actor. A
self-targeted SEND is rejected during law validation and creates no message,
message event, or recipient-visible history. The existing cognition opportunity
is not replaced or retried. SEND to another active listed peer is unchanged.

## Consequences

- Agent-visible addressability and domain-valid addressability agree.
- No self-message channel is introduced implicitly.
- This resolves an existing baseline ambiguity; it does not add an action,
  communication channel, reward, or social semantic.
- Resolution of this blocker is required before M2.

ARC-300 continues to own ContextPack visibility. The action-intent machine
contract owns the field-level invariant, and the Law Validator enforces it.
