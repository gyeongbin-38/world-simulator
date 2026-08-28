# Architecture Change Policy

This document answers one question:

> When is a change ordinary implementation work, and when must architecture be reopened?

## C0 — Implementation change

Examples:
- refactoring;
- storage library choice inside an existing adapter boundary;
- batch size tuning that preserves semantics;
- cache sizing;
- UI styling.

Requirement:
- existing owner documents/tests remain valid.

## C1 — Adapter change

Examples:
- new model runtime backend;
- new Observatory client;
- new artifact storage adapter.

Requirement:
- preserve foundation semantics;
- add conformance evidence before treating the adapter as supported.

## C2 — Domain-contract change

Examples:
- ActionIntent meaning;
- proposal lifecycle;
- message visibility timing;
- lifecycle timing;
- canonical ownership;
- agent-visible information.

Requirement:
- update owning architecture document before implementation;
- update regression/fault/conformance tests.

## C3 — Foundation-breaking change

Examples:
- model directly mutates world state;
- UI coordinates become causal without an explicit physical environment;
- central mate fitness appears in EXP-000;
- infrastructure failures become ecological death;
- exploration/confirmation separation is removed.

Requirement:
- explicitly reopen the foundation decision;
- record rationale and affected experimental validity.

## Just-in-time architecture

Future planned views are authored immediately before their implementation gate.

Do not create speculative deep documents that have no near-term implementation owner.
