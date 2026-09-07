# WORLD RESEARCH PROGRAM V1

Status: **ACTIVE EXPLORATION PROGRAM / NOT A GLOBAL PREREGISTRATION**

Base milestone: EXP-000 minimum artificial-life engine closed at `2724025776e554528a038cbdc57078d3b9c0bb1c`.

This document restores the project to its original scientific purpose: use a durable multi-agent artificial-life world to test whether social structure, emotion-like dynamics, cultural transmission, and heritable capability change can emerge from repeated interaction and reproduction.

It is intentionally less rigid than a preregistration. The project will use two stages:

1. **Exploration** — cheap, small, fast studies used to discover whether a phenomenon exists and to improve measurement.
2. **Confirmation** — only after a phenomenon looks real, freeze the hypothesis, controls, metrics, seeds, run budget, and exclusion rules before a larger canonical run.

Negative and null results are valid outcomes. The project must never redesign a hypothesis after seeing a result and then present it as if it were preregistered.

---

## 1. Scientific objective

The World Simulator is not primarily a game engine or a UI project. Its core purpose is to study artificial populations of language-model agents across interaction, social feedback, environmental pressure, reproduction, learning, and generational change.

The main scientific questions are:

1. **Social emergence:** Can repeated communication alone produce persistent, non-random social relationships without explicit friendship, trust, romance, faction, or reputation variables?
2. **Synthetic affect:** Can anonymous private latent modulators, visible only through their behavioral consequences, produce stable emotion-like social dynamics through feedback between agents?
3. **Neural heredity:** If agents acquire individual neural adaptations during life and descendants inherit recombined/mutated parental adaptations, do later generations outperform appropriate non-heritable controls?
4. **Cultural ecology:** When unknown objects/resources have hidden consequences, can agents discover effects, transmit knowledge, preserve it beyond the discoverer's lifetime, and reorganize behavior under scarcity or opportunity?

These four axes define the CORE program.

---

## 2. What EXP-000 established — and what it did not

EXP-000 established an engineering baseline:

- real-model cognition can drive a continuous multi-agent trajectory;
- agents can SEND, PROPOSE, ACCEPT/REJECT under world law;
- bilateral reproduction can produce canonical children;
- children can later enter cognition;
- natural death, lineage, durable SQLite state, CAS evidence, and replay work;
- attempted actions are separable from committed world events.

The final 3-founder × 20-tick live grounding pilot was an **engineering admission run**, not the definitive social-emergence experiment.

EXP-000 did **not** establish:

- stable social structure;
- spontaneous friendship, trust, hostility, attachment, or reputation;
- cultural persistence;
- synthetic emotion;
- inherited learning;
- generational capability improvement;
- resource-driven cooperation or competition;
- language/convention evolution;
- civilization.

The next studies must answer those questions directly rather than extending the engineering baseline indefinitely.

---

## 3. Program-wide scientific rules

These rules apply across all studies unless a study explicitly replaces them.

### 3.1 Separate mechanism from interpretation

Do not encode the phenomenon we claim to discover.

Examples:

- If testing friendship, do not add `friendship_score`.
- If testing reputation, do not add a canonical `reputation` variable.
- If testing love/attachment, do not label a private state `love`.
- If testing emergent language, do not predefine the intended symbol meanings.

The world may contain mechanistic variables necessary to support a study, but the scientific label should usually be assigned from measured behavior after the fact.

### 3.2 Avoid anthropomorphic overclaim

The project may report **relationship-like**, **attachment-like**, **grief-like**, **reputation-like**, or **emotion-like** dynamics when operational metrics support those descriptions.

It must not claim that an LLM literally feels human emotion merely because it exhibits a behavioral analogue.

### 3.3 Attempt is not commit

A selected model action is not automatically a canonical event.

Metrics must preserve the distinction among:

- action selected;
- payload generated;
- Gateway intent;
- LawValidator admission/rejection;
- canonical committed world event.

### 3.4 Use multiple seeds for claims

Single trajectories are useful for exploration and qualitative discovery, but not for population-level claims.

Confirmation studies should use enough seeds to estimate variability and uncertainty. Exact seed counts are study-specific and should be chosen after an exploratory variance estimate rather than fixed globally now.

### 3.5 Match compute/inference budgets where comparison requires it

When comparing individual vs group performance, culture vs heredity, or different social conditions, do not let one condition win simply because it received more total model calls or tokens unless extra compute is itself part of the intervention.

### 3.6 Preserve all results

Failed, null, and anomalous runs remain part of the record.

No post-hoc deletion of inconvenient runs unless a preregistered integrity failure criterion is met.

### 3.7 UI is instrumentation, not authority

Live World / Observatory views may visualize the experiment, but canonical science remains in world state/evidence. Visualizations must not create or repair events.

---

# PART I — CORE RESEARCH AXES

## 4. CORE A — Emergent Social Structure in a Blank World

### 4.1 Main question

Can persistent social structure emerge when agents are given communication and reproduction opportunities but no explicit friendship, trust, faction, emotional, spatial, or resource variables?

### 4.2 Why this should come first

This is the cleanest behavioral baseline because the current engine already supports communication, proposal, reproduction, lineage, and death.

If rich structure appears here, later interventions can be measured against it. If nearly all agents WAIT or interact randomly, that is also important because it establishes how much additional mechanism is required to create social dynamics.

### 4.3 Exploratory phenomena

Measure whether the following arise above matched null/shuffled baselines:

- repeated dyadic interaction;
- reciprocity;
- partner selectivity;
- stable pair persistence;
- non-random mate/proposal preference;
- asymmetric centrality / communication hubs;
- persistence of relationships across time;
- third-party information effects;
- reputation-like avoidance/preference;
- gossip / information propagation;
- parent-child preferential interaction if genealogy is observable to agents.

### 4.4 Candidate metrics

Do not freeze all of these globally. Exploration should determine which are robust enough for a confirmatory paper.

- interaction entropy per agent;
- dyad persistence relative to shuffled partner labels;
- reciprocity coefficient;
- repeated-contact probability;
- partner-selectivity index;
- proposal/mate-choice concentration;
- network modularity / clustering where sample size supports it;
- centrality persistence;
- third-party behavioral change after receiving information about another agent;
- reputation propagation depth;
- false-information correction rate;
- relationship survival across lifecycle boundaries.

### 4.5 Controls

Candidate controls include:

- partner-label shuffle over an identical event sequence;
- memory/context ablation;
- randomized partner choice with matched action rate;
- reduced-history condition;
- no-communication or communication-limited baseline where scientifically useful.

### 4.6 Provisional Paper 1

**Emergent Social Structure in a Blank Language-Model Society**

Likely primary story:

> With no explicit relationship variables, do repeated interactions become persistently structured and predictive of future communication or reproduction choices?

The paper is viable only if effects replicate across seeds and survive simple null models.

---

## 5. CORE B — Synthetic Affect and Social Feedback

### 5.1 Main question

Can private, anonymous internal modulators create stable emotion-like behavioral dynamics when other agents can observe only their outward behavior and language?

### 5.2 Mechanistic principle

Do not expose a state called `happy`, `sad`, `angry`, `love`, or `fear` as the causal variable.

Instead use anonymous latent dimensions or neuromodulatory channels that influence bounded components such as:

- memory salience;
- retrieval priority;
- attention allocation;
- exploration/exploitation tendency;
- social approach/avoidance tendency;
- persistence of particular social memories;
- action priors where justified.

Another agent must infer the first agent's state from behavior, not read the private latent directly.

### 5.3 Core feedback loop

`private state A → A behavior/language → B interpretation and response → A observes B → A future state/behavior`

The research question is whether this loop produces durable population-level dynamics without explicit emotion labels.

### 5.4 Primary comparison arms

A clean initial comparison is:

1. **No Affect** — no private modulation.
2. **Explicit Emotion** — conventional named emotional-state baseline if needed for comparison.
3. **Anonymous Neuromodulation** — private unlabeled latent modulators.

### 5.5 Candidate phenomena

- attachment-like pair persistence;
- avoidance-like persistence;
- social contagion / downstream behavioral propagation;
- relationship-dependent memory salience;
- loss/grief-like change after a persistent partner dies;
- recovery time after social loss;
- affect-dependent mate preference;
- hysteresis: behavior remains altered after immediate stimulus disappears.

### 5.6 Candidate metrics

- state-to-behavior coupling;
- partner-conditioned interaction probability;
- persistence half-life of a social bias;
- behavioral change after partner death vs matched unrelated death;
- network propagation depth of induced behavioral changes;
- recovery curve after perturbation;
- mutual-information-style dependence between private latent history and future social actions, with leakage controls.

### 5.7 Important claim boundary

Even strong results support **functional emotion-like dynamics**, not proof of subjective consciousness or human feeling.

### 5.8 Provisional Paper 2

**Synthetic Affect Through Private Neuromodulation and Social Feedback in Language-Model Agents**

---

## 6. CORE C — Cultural Ecology and Resource Discovery

### 6.1 Main question

When agents encounter unknown environmental objects with hidden effects, can useful knowledge be discovered, communicated, preserved, distorted, and transmitted across generations?

### 6.2 Why resources should be introduced gradually

Do not jump directly from blank society to a complex economy.

A staged ecology preserves causal interpretability:

1. inert/placebo objects;
2. hidden-effect objects;
3. useful but non-scarce resources;
4. scarcity/competition;
5. storage or environmental modification;
6. richer ecological interactions.

### 6.3 Canonical discovery template

Example:

- Object `R1` has no semantic name indicating its purpose.
- Using R1 has a hidden measurable effect, such as extending lifespan or improving a bounded capability.
- Agents are not told the causal rule.
- An agent may discover the effect through experience.
- Knowledge may spread through messages or observation.

Measure whether the information survives after the original discoverer dies.

### 6.4 Candidate phenomena

- discovery latency;
- independent rediscovery;
- transmission fidelity;
- cumulative cultural retention;
- misinformation and correction;
- teaching-like behavior;
- resource hoarding;
- sharing/cooperation;
- competition;
- division of labor;
- shared conventions for unnamed objects;
- persistent culture after founder extinction.

### 6.5 Key controls

- inert placebo object;
- same visual/object identity with hidden effect removed;
- effect present but communication disabled;
- communication present but no persistent memory/cultural storage;
- optional shared board/library vs message-only culture.

### 6.6 Candidate culture metric

A particularly important measure is **post-discoverer persistence**:

> Does correct behavioral knowledge remain in the population after every agent that directly experienced the original discovery is dead?

This separates transient imitation from stronger cultural transmission.

### 6.7 Provisional Paper 3 or 4

**Cultural Transmission and Hidden-Resource Discovery Across Artificial Generations**

Paper order may change depending on which phenomenon becomes robust first.

---

## 7. CORE D — Neural Heredity and Generational Capability Change

### 7.1 Main question

If agents acquire individual learned neural adaptations during life, and descendants inherit recombined/mutated parental adaptations, do later generations show measurable improvements over non-heritable controls?

This is one of the highest-value but highest-cost studies in the program.

### 7.2 Required mechanism

The eventual implementation should separate:

- shared base model;
- individual lifetime adaptation;
- parent adapter/genome representation;
- crossover/recombination;
- bounded mutation;
- child adapter construction;
- lineage/provenance;
- evaluation independent from training experience.

LoRA/adapters are a practical initial mechanism, not a claim that biological genetics is being literally replicated.

### 7.3 Core 2×2 inheritance design

Use a factorial comparison:

| Condition | Cultural transmission | Neural heredity |
|---|---:|---:|
| Neither | No | No |
| Cultural only | Yes | No |
| Genetic only | No | Yes |
| Both | Yes | Yes |

This is critical. If descendants improve, the project must distinguish information learned socially from parameter changes inherited neurally.

### 7.4 Primary outcomes

Do not define improvement only as survival if survival is directly shaped by a resource rule.

Use at least two classes of evaluation:

1. **Ecological performance** — success inside the world under held-out or controlled environmental challenges.
2. **Held-out capability battery** — tasks not directly experienced during adaptation, chosen to test whether inheritance produced transferable change rather than memorization.

Possible outcomes:

- descendant vs parent performance;
- descendant vs same-generation no-heredity control;
- rate of adaptation after birth;
- robustness under novel environmental perturbation;
- lineage-level accumulation vs regression;
- mutation load / catastrophic drift.

### 7.5 Essential controls

- random/untrained adapter inheritance baseline;
- same compute budget across arms;
- mutation-only control;
- crossover-only control;
- no-heredity child with identical cultural exposure;
- frozen evaluation set hidden from lifetime adaptation where possible.

### 7.6 Falsification examples

The heredity hypothesis is weakened if:

- later generations do not beat matched non-heritable controls;
- apparent gains disappear under equal compute/token budget;
- gains exist only on training experiences but not held-out tasks;
- mutations cause uncontrolled degradation with no reproducible selection advantage.

A null result here is scientifically informative.

### 7.7 Provisional Paper 3

**Neural Heredity in Language-Model Artificial Life: Recombination, Mutation, and Generational Capability Change**

---

# PART II — SECONDARY AND WILDCARD STUDIES

## 8. SECONDARY candidates

These are strong candidate studies that can be promoted to CORE if exploratory effects are robust.

### 8.1 Reputation without a reputation variable

Can third-party information alter later partner choice or avoidance without a canonical trust/reputation score?

### 8.2 Gossip and misinformation

Can claims about absent agents propagate through a network, persist after contradiction, or be corrected by direct evidence?

### 8.3 Emergent symbolic convention / proto-language

Can agents converge on arbitrary labels or symbols for unnamed objects/actions, and do those conventions persist across generations?

A strong test is whether a convention survives the death of its original creators.

### 8.4 Mate preference and assortative mating

Does social history predict who receives reproduction proposals? If mate choice becomes non-random, does assortative mating alter later evolutionary dynamics?

### 8.5 Parent-child behavior

When genealogy is visible but no parental-love rule exists, do parents preferentially communicate with, teach, protect, or reproduce cultural information to offspring?

### 8.6 Social contagion

If only one agent receives a private modulation, do behavior patterns propagate through unmodulated agents via interaction alone?

### 8.7 Division of labor

Under ecological tasks, do agents specialize into persistent roles without explicit role assignment?

### 8.8 Collective intelligence

Under equalized total inference/token budgets, does a communicating group outperform a single agent or non-communicating group on bounded tasks?

---

## 9. WILDCARD candidates

These are high-upside but should not distract from the core program prematurely.

### 9.1 Niche construction / environmental inheritance

Agents modify the environment; descendants inherit the changed world rather than neural parameters or direct messages.

This creates a third inheritance channel:

- neural inheritance;
- cultural inheritance;
- environmental inheritance.

### 9.2 Norms and punishment

Can repeated interaction generate stable behavioral norms or sanctions without a hard-coded morality score?

### 9.3 Coalition and proto-institution formation

Do persistent coalitions, coordination conventions, leadership, or governance-like structures appear under shared ecological pressure?

### 9.4 Cultural drift and population divergence

If two initially identical populations are isolated, do conventions, partner structures, or resource practices diverge across seeds/time?

### 9.5 Taboo-like convention

Can arbitrary avoidances become culturally persistent without the environment continuing to justify them?

This is scientifically interesting but requires especially careful interpretation.

---

# PART III — EXPERIMENT OPERATING MODEL

## 10. Exploration vs confirmation

### 10.1 Exploration stage

Purpose:

- discover whether a signal exists;
- debug mechanisms;
- estimate variance/effect size;
- improve metrics;
- find failure modes.

Exploration may use:

- fewer agents;
- shorter horizons;
- fewer seeds;
- local/quantized models when clearly labeled as a different runtime regime;
- flexible analysis.

Exploratory findings must be labeled exploratory.

### 10.2 Confirmation stage

Once a phenomenon looks promising, freeze a study-specific protocol containing:

- exact research question;
- primary hypothesis;
- intervention;
- controls;
- primary/secondary metrics;
- seed set or seed-generation procedure;
- agent count;
- horizon;
- model/runtime identity;
- stopping rules;
- integrity gates;
- exclusions;
- analysis method.

Only then run the larger canonical experiment.

This gives the project publication-grade discipline without making early exploration unbearably rigid.

---

## 11. Local vs VM compute policy

Not every experiment belongs on an A40/VM.

### 11.1 Local machine responsibilities

Use local compute for:

- environment/mechanism development;
- deterministic unit tests;
- metric validation;
- replay/Observatory work;
- tiny exploratory runs;
- schema/provenance checks;
- cheap ablations;
- feasibility testing.

A local quantized runtime may be useful for exploration, but results must not be silently compared as if they were identical to the frozen A40 runtime.

### 11.2 VM/A40 responsibilities

Use VM compute for:

- canonical model regime reproduction;
- larger populations/horizons;
- multiple confirmatory seeds;
- training/adaptation-heavy heredity experiments;
- final controlled ablations;
- publication-grade confirmatory runs.

### 11.3 VM Admission Gate

Do not start paid GPU compute until all applicable items are ready:

- research question is written;
- intervention/control distinction is clear;
- primary metrics can be computed on synthetic/local fixtures;
- code and deterministic tests pass;
- expected output/evidence schema is known;
- failures will still preserve evidence;
- seeds are defined;
- approximate GPU budget is estimated;
- exploratory/local pilot gives a reason to spend on the larger run.

VM debugging should be exceptional, not the normal development workflow.

---

## 12. Recommended experiment order

The order below minimizes new causal variables and cost.

### Stage R0 — Restore research baseline

- freeze this research program;
- retain EXP-000 engineering closure;
- define reusable social-network/interaction metrics;
- add optional Live World instrumentation without changing scientific truth.

No paid GPU required.

### Stage R1 — Blank-world social exploration

Start with a larger/longer blank population than the engineering pilot.

Goals:

- measure spontaneous communication rate;
- quantify WAIT dominance;
- test pair persistence, reciprocity, partner selectivity, mate preference;
- inspect reputation/gossip candidates.

Do cheap local feasibility first, then a bounded canonical VM pilot if justified.

### Stage R2 — Confirm social-emergence signal

If R1 yields a robust candidate phenomenon:

- freeze Paper-1 protocol;
- run multiple seeds and controls;
- test null/shuffle models;
- produce first scientific paper candidate.

### Stage R3 — Synthetic affect exploration

Add only the private affect mechanism and appropriate controls.

Do not add resources or heredity yet.

Goal: causal comparison against blank-world social baseline.

### Stage R4 — Cultural ecology

Add inert/hidden-effect objects, then progressively stronger ecological structure.

Measure discovery, transmission, persistence, misinformation, cooperation/competition, and emergent conventions.

### Stage R5 — Neural heredity

Only after lifetime adaptation and evaluation infrastructure are trustworthy:

- implement individual adapters;
- inheritance/recombination/mutation;
- 2×2 Culture × Heredity design;
- held-out performance battery;
- generational analyses.

This is expected to be the most compute-intensive core program.

### Stage R6 — Combined worlds

Only after individual mechanisms are understood, study interaction among:

- social structure;
- synthetic affect;
- culture;
- resources;
- heredity.

Do not begin here. Combined complexity is scientifically interesting only after component effects are characterized.

---

## 13. Minimal publication-grade standard

A result should not be promoted as a paper-level claim solely because one trajectory looks interesting.

At minimum, a serious claim should generally have:

- a clear question;
- at least one meaningful control/null model;
- repeated seeds or independent runs;
- a prespecified primary metric for the confirmatory phase;
- uncertainty/effect-size reporting, not only screenshots;
- exact model/runtime/data provenance;
- preserved negative runs;
- mechanistic or ablation evidence where the claim is causal;
- bounded language that matches what was actually measured.

This is intentionally a minimum, not an exhaustive publication checklist.

---

## 14. Observability requirements for future studies

Every new scientific mechanism should remain observable without letting the UI become world authority.

Useful live/replay event categories include:

- cognition started/finished — telemetry only when non-canonical;
- action selected;
- Gateway intent;
- Law admission/rejection;
- message committed;
- proposal created/resolved;
- birth committed;
- death committed;
- resource interaction committed;
- adaptation checkpoint committed;
- inheritance/genome artifact committed.

A future Live World UI may show speech bubbles, proposal/birth/death animation, and agent activity in real time, but scientific analyses must continue to use canonical evidence rather than visual appearance.

---

## 15. Decision rules for promoting new ideas

A Secondary/Wildcard idea may become CORE if it satisfies most of:

- effect is visible across more than one seed;
- not trivially explained by prompt wording;
- measurable quantitatively;
- has a credible control/null model;
- connects to a broader scientific literature/question;
- can be isolated without adding many confounds;
- result would remain interesting even if the hypothesis is false.

This keeps the project open to surprising phenomena without becoming an uncontrolled collection of features.

---

## 16. Immediate next actions

1. Treat this document as the top-level scientific roadmap, not as a global preregistration.
2. Keep `observatory-ui-v1` as instrumentation work; do not let UI polish delay the science program.
3. Design **R1 Blank-World Social Exploration V1** as the first new scientific study.
4. Before paid compute, implement/validate the social metrics and null models locally.
5. Estimate local inference feasibility separately from the canonical A40 regime.
6. Only after R1 exploratory data exists decide whether Paper 1 should emphasize pair persistence, mate preference, reputation/gossip, or another emergent social signal.

---

## 17. Program thesis

The project is ultimately testing whether increasingly rich artificial-life phenomena can arise when a language-model population is given memory, interaction, reproduction, private internal modulation, environmental consequences, learning, and inheritance — while carefully separating which mechanism caused which effect.

The intended progression is:

`interaction → relationship structure → social feedback → culture/ecology → lifetime adaptation → heredity → generational change`

The project succeeds scientifically not by forcing this progression to occur, but by measuring honestly which parts emerge, which require explicit mechanisms, and which fail under controlled comparison.
