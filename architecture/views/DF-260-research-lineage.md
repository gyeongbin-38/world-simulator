# DF-260 — Research Data & Causal Lineage

**Status:** REVIEWED  
**Parent:** ARC-200  
**Question:** How does a scientific claim trace back to exact experimental evidence?

## Principle

```text
interesting observation
!=
confirmatory result
```

A-LifeLM must preserve an auditable path:

```text
experiment definition
→ run
→ snapshot/context/raw model output
→ proposed/validated/committed behavior
→ immutable events/evidence
→ derived dataset
→ analysis definition
→ result
→ figure/table
→ claim
```

## Exploration

Exploratory work may:
- inspect behavior;
- create new metrics;
- manually intervene;
- notice unexpected structures;
- create hypotheses.

Exploratory evidence must remain labeled exploratory.

## Confirmation

Before confirmatory run outcomes are inspected:
- hypothesis/primary question is frozen;
- confirmatory run condition is frozen;
- primary analysis/exclusion/censoring rules are frozen;
- fresh confirmatory runs are used.

Changing primary analysis after viewing outcomes creates a post-hoc/exploratory analysis or requires a fresh confirmation cohort.

## Immutable derivation

Derived data is regenerated through registered transformations rather than edited in place.

A result must resolve:
- source run cohort;
- included/excluded/censored status;
- source event/evidence scope;
- metric/analysis definition;
- code/environment identity where required;
- random analysis seed when applicable.

## Censoring

`CENSORED_CAPACITY` is not ordinary completion.

Confirmatory analysis must predeclare whether censored runs are:
- excluded under a frozen rule;
- included only up to the censor boundary under a censor-aware method;
- explicitly modeled as an outcome.

Runs cannot be removed merely because results are inconvenient.

## Qualitative evidence

A quoted/paraphrased agent interaction must be traceable to:
- run/tick;
- committed message/action identity;
- raw payload/model output;
- relevant ContextPack/evidence;
- experiment condition.

Researcher labels such as "attachment-like" or "leader-like" are derived annotations, not canonical world state.

## Figures and tables

A figure/table is presentation, not numerical authority.

It must be reproducible from registered derived results/data. Manual spreadsheet edits cannot silently replace the analysis source.

## Claim registry concept

A manuscript claim should be traceable to:
- hypothesis/claim class;
- supporting results;
- analysis definition;
- datasets;
- included/excluded run cohort;
- censoring/limitations;
- underlying event/raw-evidence lineage.

This traceability is required for paper-ready results.
