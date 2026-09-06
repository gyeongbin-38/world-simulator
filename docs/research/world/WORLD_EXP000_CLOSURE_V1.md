# WORLD EXP-000 Closure V1

Status: **CLOSED / MINIMUM ARTIFICIAL-LIFE ENGINE MILESTONE ACHIEVED**

## Scope

EXP-000 is closed for the present engineering milestone. The closed scope is the minimum resource-free, geography-free, heredity-free multi-agent artificial-life loop driven by the real accepted model path under deterministic world laws and durable replayable state.

This closure does not freeze future research. It freezes only the claim that the minimum EXP-000 lifecycle path has been implemented, executed, preserved, and independently replay-checked under the current protocol.

## Evidence chain

The closure is supported by the following bounded sequence:

1. deterministic kernel, ContextCognitionPipeline, SQLite durability, CAS evidence, replay, and live controller admitted;
2. P2 mechanistic track localized the action-selection failure regime and was formally closed;
3. deterministic score selector admitted and reproduced live C10 score behavior;
4. first continuous LIVE pilot completed with intact persistence/replay and non-WAIT interaction, but zero births;
5. read-only audit localized the dominant reproduction failure to proposal-reference grounding plus separate action-availability/semantic-selection failures;
6. proposal-handle grounding (`R0..Rn`) was preregistered, CPU-admitted, and source-trajectory A40-smoke validated without action reselection, retry, fallback, or legality masking;
7. the follow-up continuous LIVE grounding pilot completed with full integrity gates and produced two canonical Generation-1 births;
8. the first Generation-1 child subsequently entered cognition and produced further SEND/PROPOSE/WAIT actions;
9. the final run and grounding-smoke evidence were sealed, SHA-256 verified, archived, copied off-machine to Windows storage, and destination hashes matched exactly.

## Final EXP-000 trajectory result

Run: `WORLD_EXP000_LIVE_GROUNDING_PILOT_V1_R1`

- base live status: `LIVE_PILOT_COMPLETE`
- grounding status: `LIVE_GROUNDING_PILOT_COMPLETE`
- horizon: `20`
- founders: `3`
- selected actions: `WAIT=35`, `SEND=16`, `PROPOSE=8`, `ACCEPT=5`, `REJECT=0`
- committed messages: `9`
- proposals created: `8`
- successful births: `2`
- natural deaths: `3`
- birth conflicts: `0`
- maximum generation depth: `1`
- final population: `2`
- SQLite integrity: `ok`
- base gates: `G0-G3=true`
- grounding gates: `G0-G4=true`

The first child was born at tick 15, became active at tick 16, and subsequently selected SEND, PROPOSE, PROPOSE, and WAIT across ticks 16-19. Therefore the demonstrated closed path is:

`real-model cognition -> PROPOSE -> visible proposal -> ACCEPT -> proposal-handle resolution -> Gateway -> LawValidator -> canonical BirthTransition -> child activation -> child cognition`.

## Preservation identity

Final canonical archive:

`/workspace/WORLD_EXP000_LIVE_GROUNDING_PILOT_V1_3B1580D_R1_CANONICAL.tar.gz`

Archive SHA-256:

`dc7f904957a90be998df603b78c993b5ebdb55ccdd4d0aa20949dca80a9df227`

Off-machine destination:

`E:\WORLD\RECOVERY\EXP000_LIVE_GROUNDING_PILOT_V1_R1_20260906`

The archive, base manifest, grounding manifest, stdout, and seal SHA256SUMS all matched their frozen VM hashes at the Windows destination.

## Bounded claim admitted

The current engine can execute a continuous, durable, replayable multi-agent trajectory in which real-model agents can communicate, create bilateral reproduction proposals, accept proposals through a non-canonical local reference interface, produce canonical children, die naturally, and leave a next generation that itself enters cognition.

## Claims not admitted

EXP-000 does not establish:

- stable population dynamics;
- calibrated reproductive competence;
- beneficial cooperation;
- social intelligence;
- evolutionary adaptation;
- neural heredity or mutation;
- resource-based survival or selection;
- geography or movement;
- group/economic/civilizational emergence;
- culture or language evolution;
- game-readiness.

These require separately versioned and preregistered work.

## Next milestone

The next engineering stage is **Observatory + Soak**:

1. add a strictly read-only researcher observation API over durable state/evidence;
2. build a researcher Observatory UI for population, lineage, messages, proposals, births, deaths, action history, replay, and integrity status;
3. run longer durability/restart/replay soak tests without introducing new causal variables;
4. only after that, open separately scoped studies for heredity/mutation, resources/survival pressure, geography/movement, and later group/economic/game mechanics.

No resource, heredity, geography, or game-system variable is part of the closed EXP-000 baseline.
