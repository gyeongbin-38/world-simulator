# A-LifeLM · World Simulator

**An independent research project on environmental information persistence and action selection in language-model agents.**

## Motivation

This project began with a question: **can an agent leave information in its environment that helps another agent complete a task?** It explores how interactions change with environmental rules and information access, without assigning cooperative strategies or social roles to agents in advance.

To investigate this, I built a deterministic simulation kernel, model action interfaces, experimental protocols, and evidence storage and audit tools. The platform separates model proposals from committed actions and preserves execution state across interruptions.

## Work and findings

| Research track | Approach | Findings to date |
|---|---|---|
| Experimental platform · EXP-000 | Real-model multi-agent runs with communication, births, deaths, and preserved evidence | Implemented and recorded the minimum execution path; separately verified restart, fault recovery, and replay consistency using a deterministic policy runtime |
| Environmental information persistence · EXP-STIG-001–006 | Varied persistence requirements, inter-agent dependence, model cohorts, and TRACE/REUSE conditions | Under bounded conditions, observed OLMo writing peer-needed information into environmental world state and SmolLM3 using it to complete a task |
| Failure analysis | Examined persistent trace writing and internalization separately | TRACE was rarely selected and REUSE was never observed; world-state persistence and TRACE/REUSE outcomes remain distinct |
| Model adaptation · Foundation / P1 / P2 | Adapter and WORLD-prefill comparisons, followed by KV-cache interventions | Partially localized causal effects on the selector; the follow-up F0 A/B training comparison remains pending its resource gate |

Complementary model behaviors were observed rather than assigned as roles. The current contribution is **an experimental platform and initial observations under bounded conditions**. Small model cohorts and short horizons limit generalization; these results do not establish general cooperation, evolutionary adaptation, or cultural emergence.

## Research materials and code

The latest experimental code and organized documentation are on the **[`docs/research-portfolio` research branch](https://github.com/gyeongbin-38/world-simulator/tree/docs/research-portfolio)**. The implementation on the default `master` branch predates that research branch; this page provides an overview of the broader project.

- [Research overview and quick start](https://github.com/gyeongbin-38/world-simulator/blob/docs/research-portfolio/README.md)
- [Experiment designs and results index](https://github.com/gyeongbin-38/world-simulator/blob/docs/research-portfolio/docs/research/README.md)
- [Integrated EXP-STIG findings and limitations](https://github.com/gyeongbin-38/world-simulator/blob/docs/research-portfolio/docs/research/world/EXP-STIG-INTEGRATION.md)
- [EXP-000 implementation and execution scope](https://github.com/gyeongbin-38/world-simulator/blob/docs/research-portfolio/docs/research/world/WORLD_EXP000_CLOSURE_V1.md)
- [P2 mechanistic analysis](https://github.com/gyeongbin-38/world-simulator/blob/docs/research-portfolio/docs/research/world/WORLD_P2_MECHANISTIC_TRACK_CLOSURE_V1.md)
- [Reproduction instructions and evidence availability](https://github.com/gyeongbin-38/world-simulator/blob/docs/research-portfolio/docs/REPRODUCIBILITY.md)

The research branch's GPU-free quick start passed documentation checks and all 53 selected contract, kernel, and recovery tests during the portfolio review. Raw experimental evidence is stored separately, so cloning the repository alone does not enable a complete re-audit of every historical model result. Next steps are repeated validation of key findings and preparation of public evidence packages.

The original experimental records are in English. The newly added research index, reproduction guide, and publication status note are currently in Korean.
