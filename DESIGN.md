# DESIGN.md — A-LifeLM Compact System Map

This is a compact orientation map. It does not redefine detailed lifecycle, reproduction, tick, or research rules.

## Mission

A-LifeLM investigates whether populations of minimally socially constrained language-model agents can develop persistent communication, reproductive structure, lineage dynamics, cultural transmission, and later environmental adaptations under controlled and reproducible experiments.

The initial experiment family is `EXP-000`: a deliberately sparse social baseline.

## System

```text
Researcher
    ↓
Experiment Controller
    ↓
Simulation Kernel
    ├─ Context Compiler → Model Runtime → ActionIntent
    ├─ Communication
    ├─ Reproduction
    ├─ Lifecycle
    └─ Intervention boundary
    ↓
Validation + Commit
    ├─ Canonical State
    ├─ Immutable Events / Evidence
    └─ Raw Artifacts
         ├─ Analysis
         └─ Observatory
```

Core authority:
- model proposes;
- deterministic laws validate;
- the commit boundary mutates canonical state;
- analysis interprets;
- Observatory visualizes.

## EXP-000

EXP-000 intentionally starts without:
- assigned personality or role;
- friend/enemy/trust variables;
- resource economy;
- causal physical geography;
- synthetic affect;
- semantic self-journaling memory;
- central mate/fitness selection;
- neural heredity.

It includes:
- finite equal baseline lifespan;
- maturity and reproduction refractory timing;
- directed language communication;
- bilateral reproduction protocol;
- birth/death/lineage evidence;
- deterministic bounded agent-visible history;
- barrier-synchronized cognition.

Exact rules are owned by the architecture views in `architecture/INDEX.md`.

## Reference implementation direction

```text
Windows workstation
├─ IDE / launcher
├─ optional Observatory process
└─ WSL2 Ubuntu
   ├─ Python research runtime
   ├─ model runtime
   ├─ active durable state
   ├─ raw artifact handling
   ├─ tests
   └─ analysis/export
```

Linux/WSL2 is the primary research runtime. Windows is the host environment.

Storage roles, not drive letters, matter:
- hot/active state on fast storage where possible;
- large model/raw/checkpoint archives on large durable storage;
- RAM/VRAM are compute/cache, never truth.

## Model strategy

Start with a deterministic fake model backend.

Only after the causal kernel passes deterministic and fault tests should a real open-weight model be connected.

Agent count should not imply one complete model copy per agent; a shared immutable base-model residency is preferred where the runtime permits it.

## Observatory

The Observatory is a read-only scientific projection.

It will eventually show:
- one unique creature sprite per living agent;
- committed messages, births, deaths;
- agent inspector;
- genealogy;
- communication network;
- experiment timeline;
- replay.

Visual details are owned by `docs/observatory/SPRITES.md`.

## Current implementation boundary

Current work may implement:
- domain types;
- ExperimentManifest handling;
- deterministic fake cognition;
- barrier tick;
- SEND / WAIT;
- reproduction proposal lifecycle;
- birth/death/refractory laws;
- in-memory commit and tests.

Persistence/replay details, full Context Fabric, experiment-control UI, scalable batching, Observatory transport, and neural heredity are intentionally authored just-in-time before their implementation gates.
