# LC-210 — Agent Lifecycle

**Status:** REVIEWED  
**Parent:** ARC-200  
**Question:** When does an agent exist, act, mature, reproduce, and naturally die?

## Canonical lifecycle

EXP-000 does not model `IMMATURE`, `MATURE`, or `REFRACTORY` as competing mutable life states.

The canonical terminal distinction is:

```text
NONEXISTENT
    ↓ birth/founder creation
ALIVE
    ↓ natural lifespan boundary
DEAD
```

Maturity and reproduction refractory status are deterministic predicates derived from tick fields.

## Founder timing

Founders:
- exist in `S_0`;
- `first_active_tick = 0`;
- may receive their first cognition opportunity at tick 0.

## Offspring timing

A child successfully born during the commit closing tick `t`:
- is created by that commit;
- has `birth_tick = t`;
- has `first_active_tick = t + 1`;
- receives no cognition opportunity in tick `t`.

No partial/unborn AgentState exists before successful birth commit.

## EXP-000 lifespan

All baseline agents use the same fixed global lifespan parameter.

No baseline:
- random natural mortality;
- lifespan variance;
- age-related cognitive degradation;
- reproduction lifespan cost;
- resource-dependent survival.

For an agent:

```text
natural_death_tick
= first_active_tick + lifespan_ticks
```

The agent is active at tick `t` iff:

```text
alive
AND first_active_tick <= t
AND t < natural_death_tick
```

Thus the final possible cognition opportunity is `natural_death_tick - 1`.

## Natural death boundary

While closing tick `t`, an alive agent whose resulting natural-death boundary is `t+1` is removed from `S_(t+1)`.

Therefore a final-tick valid message or successful reproduction can coexist with natural death in the same commit.

Death is irreversible in EXP-000.

Infrastructure failures are not valid agent-death reasons.

## Maturity

```text
maturity_tick
= first_active_tick + maturity_delay_ticks
```

Maturity gates reproduction only. It does not gate cognition or communication.

## Reproduction refractory

After successful birth at commit tick `t`, each participating parent receives the same global refractory interval.

Refractory gates reproduction only; it does not block cognition, SEND, message receipt, or unrelated actions.

## Capacity

EXP-000 has no in-world carrying capacity.

Infrastructure population limits are external guardrails. They may censor/stop a run but never select which legitimate agent is allowed to reproduce.
