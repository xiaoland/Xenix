# L1 Plan

## Stage Goal

Define the high-level strategy for issue `#72` using the approved L0 analysis and the GitHub review comments on commit `334480f6aa8b9a527ed8b210ae7f2a68fecb245b`.

This stage is intentionally split into smaller review files. `L1-PLAN.md` is the index and decision summary. The detailed strategy lives in the sub-plan files below.

## Review Map

- `L1-PLAN-01-ARCHITECTURE.md`
  - scope boundary
  - native product flow
  - service and execution boundaries
- `L1-PLAN-02-ML-DATA-CONTRACT.md`
  - dataset inspection rules
  - model registry and schema strategy
  - best-model policy
  - persistence and filesystem direction
- `L1-PLAN-03-UI-DELIVERY.md`
  - training UI strategy
  - dependency direction
  - documentation and test strategy

## L1 Decisions

The revised L1 locks these high-level decisions:

- the feature boundary is `ml service`, not `training workflow service`
- inference remains out of scope for issue `#72`
- background ML execution will use task-scoped worker execution so the UI stays responsive and task atomicity stays explicit
- the main process remains authoritative for ML task lifecycle transitions and metadata persistence
- dataset inspection reads the registered dataset source file directly; training execution copies the dataset into the task working directory instead of using a shared temp-copy pool
- model parameters and tuning grids are defined with Pydantic models, and the UI generates parameter forms from their JSON Schema
- the legacy `./ml` directory is reference material only; the native app will implement its own ML model services with normalized dataset loading and adapter boundaries
- best-model assignment is policy-driven and must not rely on naive cross-metric comparison across unrelated model families
- the first delivered model set may still be curated, but the exact subset remains a controlled L2 design choice rather than an arbitrary L1 lock

## Approval Gate to Enter L2

L2 should proceed only if this L1 direction is accepted:

- use `ml service` terminology and boundaries throughout the native app
- keep the UI thin and schema-driven
- keep inference out of this issue
- keep task execution task-local and task-directory-based
- treat best-model selection as an explicit evaluation-policy concern
- treat target-column selection as conditional rather than universal, because unsupervised models do not require a target column
