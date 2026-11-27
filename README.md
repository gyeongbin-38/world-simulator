# A-LifeLM · World Simulator

**An independent research project on environmental information persistence, action selection, and reproducible experiments with language-model agents.**

## Motivation

This project began with a question: **can an agent leave information in its environment that helps another agent complete a task?** It explores how interactions change with environmental rules and information access, without assigning cooperative strategies or social roles to agents in advance.

Answering that question required separating model proposals from committed actions and preserving an auditable record across interruptions. The project therefore combines a deterministic simulation kernel, experimental interfaces, and evidence storage and audit tools.

## Work and findings

- **Built an experimental platform.** Recorded real-model multi-agent runs involving communication, births, and deaths. Separately verified restart, fault recovery, and replay consistency using a deterministic policy runtime. [EXP-000 scope](docs/research/world/WORLD_EXP000_CLOSURE_V1.md) · [Soak results](docs/research/world/WORLD_EXP000_SOAK_RESULT_V1.md)
- **Tested information persistence and inter-agent dependence.** Across EXP-STIG-001–006, bounded experiments recorded cases where OLMo wrote information needed by a peer into environmental world state, and SmolLM3 bound that information into a correct answer. These complementary behaviors were observed rather than assigned roles. [Integrated findings](docs/research/world/EXP-STIG-INTEGRATION.md)
- **Documented unsuccessful pathways.** TRACE was rarely selected, and REUSE was never observed. Successful world-state persistence does not establish success through the separate TRACE/REUSE channel. [EXP-STIG-006 results](docs/research/world/EXP-STIG-006-results.md)
- **Investigated adaptation and action selection.** Compared Foundation adapter and WORLD-prefill effects, then used KV-cache interventions to partially localize causal effects on the selector. The follow-up F0 A/B training comparison remains pending its resource gate. [P2 synthesis](docs/research/world/WORLD_P2_MECHANISTIC_TRACK_CLOSURE_V1.md) · [F0 execution status](specs/experiments/F0-foundation-ab-execution-v1.yaml)

The current contribution is **an experimental platform and initial observations under bounded conditions**. The studies use a small model cohort and short horizons; they do not establish general cooperation, evolutionary adaptation, or cultural emergence. Next steps are repeated validation of key findings and preparation of independently inspectable evidence packages.

## Explore the research

| Research track | Main question | Starting point |
|---|---|---|
| Environmental information persistence | Do agents leave information that helps peers solve tasks? | [EXP-STIG-001–006 integration](docs/research/world/EXP-STIG-INTEGRATION.md) |
| Model adaptation and action selection | How do interface training and adapters affect action selection? | [P2 mechanistic track](docs/research/world/WORLD_P2_MECHANISTIC_TRACK_CLOSURE_V1.md) |
| Experimental infrastructure | Can runs involving communication, births, and deaths be recovered consistently? | [EXP-000 scope](docs/research/world/WORLD_EXP000_CLOSURE_V1.md), [Soak results](docs/research/world/WORLD_EXP000_SOAK_RESULT_V1.md) |

The [research guide](docs/research/README.md) connects experimental designs, results, specifications, and code. This guide and the newly added reproduction and publication notes are currently in Korean; the linked original experimental records are in English.

## Current implementation and evidence

- **Infrastructure:** deterministic ticks, validated state transitions, SQLite/CAS evidence storage, and restart/replay paths are implemented. EXP-000 records include real-model multi-agent execution.
- **Adaptation studies:** Foundation evaluations and P1/P2 interventions are documented. The follow-up F0 A/B execution specification remains `PENDING_RESOURCE_GATE`.
- **Observation:** the [Observatory](docs/observatory/README.md) is a local, read-only viewer of preserved runs. It requires the corresponding evidence archive.
- **Evidence availability:** raw experimental evidence is stored separately. Cloning this repository alone does not enable a complete re-audit of every historical result.

Individual experiment records define the applicable conditions, exclusions, and limits of each claim.

## Quick start · No GPU required

With Python 3.12+ and `uv` installed, run from the repository root:

```sh
uv sync --locked
uv run --locked python tools/docs_lint.py
uv run --locked python -m pytest tests/contracts tests/kernel tests/live/test_exp000_soak.py -q
```

This checks documentation integrity and deterministic execution and recovery behavior. It does not run LLM inference or reproduce historical behavioral experiments. This test selection passed all 53 tests during the portfolio documentation review.

See the [reproduction guide](docs/REPRODUCIBILITY.md) for environment setup, fresh soak runs, and raw evidence availability.

## Repository structure

| Path | Contents |
|---|---|
| `src/alifelm/` | Kernel, model interfaces, persistence, experiments, and observation |
| `tests/` | Contract, kernel, model, recovery, and experiment tests |
| `tools/` | Experiment runners, evaluators, and audit tools |
| `specs/experiments/` | Versioned experiment specifications and execution status |
| `docs/research/` | Study designs, results, audits, and integrated findings |
| `architecture/` | System rules and boundary-specific design documents |
| `observatory/` | Read-only research viewer frontend |

## Design and contributions

Start with [DESIGN.md](DESIGN.md) for the system map and the [Architecture Index](architecture/INDEX.md) for authoritative rules. Code changes follow [AGENTS.md](AGENTS.md) and the [documentation policy](docs/DOCS_POLICY.md). [DF-260](architecture/views/DF-260-research-lineage.md) defines the connection between research claims and evidence.

The [publication status note](docs/PUBLICATION_STATUS.md) records outstanding work on attribution, licensing, evidence distribution, and AI-assisted contributions. Existing experimental records retain their version-specific status and limitations.
