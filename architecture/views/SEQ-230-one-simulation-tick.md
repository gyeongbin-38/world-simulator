# SEQ-230 — One Simulation Tick

**Status:** REVIEWED  
**Parent:** ARC-200  
**Question:** What exact causal ordering turns `S_t` into `S_(t+1)`?

## Tick definition

A simulation tick is not a wall-clock duration.

```text
S_t
→ equal cognition opportunity set
→ closed cognition/intent batch
→ deterministic validation/planning
→ one authoritative commit
→ S_(t+1)
```

## Frozen phase order

```text
P0  open tick
P1  bind immutable S_t
P2  enumerate active-agent opportunities
P3  compile all agent ContextPacks from S_t
P4  execute cognition
P5  close IntentBatch_t
P6  validate every intent against S_t
P7  plan agent-originated transitions
P8  plan exogenous effects effective at t+1
P9  plan next-boundary lifecycle
P10 evaluate capacity/horizon/run status
P11 atomic commit
P12 publish S_(t+1)
```

Only P11 may mutate canonical simulation state.

## Barrier rule

All EXP-000 agent cognition for tick `t` derives from the same `S_t`.

Therefore:
- the first GPU result does not act first;
- batch position has no social meaning;
- one agent cannot react to another agent's tick-`t` output in tick `t`.

## Message timing

A valid SEND committed while closing tick `t` is peer-visible no earlier than `S_(t+1)`.

A final-lifetime SEND remains valid if its sender was active in `S_t`, even when that sender naturally dies in the same commit.

## Reproduction timing

A proposal committed at tick `t` becomes actionable no earlier than tick `t+1`.

A valid acceptance of a proposal already visible in `S_t` creates a birth candidate.

LC-220 owns proposal/conflict semantics.

A successful child committed at tick `t` first participates at `t+1`.

## Lifecycle ordering

Agent actions are validated from `S_t`.

Exogenous effects declared effective at `t+1` are planned after agent-originated behavior is fixed and before final next-boundary lifecycle evaluation.

This permits a future explicit lifespan-changing intervention to affect the state that exists in `S_(t+1)` without retroactively affecting tick-`t` cognition.

## Cognition failures

Execution/infrastructure failure before valid raw output:
- retry only under the frozen infrastructure policy;
- identical request/context/randomness identity;
- unresolved failure does not silently become WAIT in confirmatory baseline.

Malformed model output after generation:
- preserve raw output;
- reject the intent;
- consume the cognition opportunity;
- do not automatically call the model again.

## Commit ordering

Deterministic serialization may use stable technical ordering only after social/domain conflicts are resolved.

Wall time, GPU completion time, task/thread order, batch position, or storage return order are forbidden ordering authorities.

## Capacity

Legitimate outcomes are not selectively rewritten merely to fit hardware.

If the configured safety boundary is reached/exceeded, the run is explicitly censored/stopped according to infrastructure policy rather than turning capacity into hidden ecology.

## Run horizon

For horizon `H`:
- execute ticks `0 ... H-1`;
- publish `S_H`;
- then complete the run unless another explicit terminal condition occurred earlier.
