# L3 Plan

## Stage Goal

Turn the approved `#72` design into an implementation roadmap that matches the real repository baseline after issue `#75`.

Current baseline:

- storage schema is already at `v2`
- `WorkItem` already owns `dataset_id`, `feature_columns`, and `target_columns`
- dataset inspection already exists in `DatasetService`
- the UI already has a working dataset workspace

Issue `#72` therefore starts from training orchestration, model persistence, worker execution, and training UI, not from dataset import.

## Review Map

- `L3-PLAN-01-STORAGE-CONTRACTS.md`
  - schema `v2 -> v3`
  - minimal `trained_model`
  - task artifact layout
- `L3-PLAN-02-ML-SERVICE-WORKER.md`
  - service boundary
  - queue and worker-process flow
  - result ingestion and best-model updates
- `L3-PLAN-03-REGISTRY-ADAPTERS.md`
  - model registry
  - model services
  - evaluation and worker contracts
- `L3-PLAN-04-UI-TESTS-DOCS.md`
  - training workspace delivery
  - test sequencing
  - docs and AGENTS updates

## L3 Execution Order

Implementation should proceed in this order:

1. storage `v3` and repository changes
2. ML contracts, evaluation policy, and registry declarations
3. service orchestration and execution manager
4. worker-process entrypoint and model services
5. UI integration on top of the existing dataset workspace
6. tests, docs, and result write-up

## Stage Decisions

This L3 draft locks the following execution choices:

- `MLService` becomes the UI-facing training boundary, but dataset inspection remains implemented in `DatasetService`
- each ML task is atomic for one model and one operation, including `EVALUATE`
- `MLService` exposes explicit workflow methods such as `fit_with_evaluate()` and `tune_with_evaluate()`
- execution-side artifact finalization is owned by a separate executor component, not by `MLService`
- the first UI delivery extends the existing native shell with a dedicated training workspace instead of replacing the dataset workspace
- worker execution remains sequential in v1, with one service-owned `multiprocessing` process at a time
- tuning stays atomic per model, while the UI may bulk-dispatch several tuning tasks
- the shared dataset temp-copy area is removed from the ML execution path during this issue

## Approval Gate To Enter Implementation

Implementation should start only if this L3 direction is accepted:

- schema advances from `v2` to `v3`
- minimal `TrainedModel` persistence is added before any worker logic lands
- training orchestration composes existing dataset/work-item services rather than re-owning their storage rules
- evaluation is implemented as a distinct persisted `MLTask`, chained only by explicit workflow methods such as `fit_with_evaluate()` and `tune_with_evaluate()`
- tuning is implemented as one task per model, even when the UI submits several together
- training UI is delivered as a new workspace beside the existing dataset workflow
