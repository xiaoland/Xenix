# L2 Plan

## Stage Goal

Define the concrete low-level design for issue `#72`: database changes, file layout, Pydantic contracts, service interfaces, worker execution flow, UI modules, and test boundaries.

This stage is split into focused files so the review can happen by concern rather than through one oversized document.

## Review Map

- `L2-PLAN-01-DOMAIN-STORAGE.md`
  - schema v2
  - filesystem layout
  - migration algorithm
- `L2-PLAN-02-SERVICES-EXECUTION.md`
  - public service APIs
  - task queue and worker execution flow
  - result ingestion algorithms
- `L2-PLAN-03-ML-CONTRACTS-REGISTRY.md`
  - Pydantic models
  - registry declarations
  - supported model set
  - evaluation policy
- `L2-PLAN-04-UI-TESTING.md`
  - UI modules
  - generic JSON-Schema form renderer
  - tests
  - module-local documentation

## L2 Decisions

This L2 draft locks the following concrete choices:

- schema version advances from `2` to `3`
- issue `#72` consumes dataset registration and inspection capabilities delivered by `#75`
- `dataset_temp_root()` and the shared dataset-copy workflow are removed from the training design
- dataset inspection metadata is ephemeral and never stored in SQLite
- a new `trained_model` table is introduced
- `work_item` gains `best_trained_model_id`
- background execution uses a single service-owned task queue with one active worker subprocess at a time
- worker requests and results are file-based and validated with Pydantic
- the first implemented model set is supervised-first:
  - `regression.linear`
  - `regression.ridge`
  - `regression.random_forest`
  - `classification.logistic_regression`
  - `classification.random_forest`
- the dynamic form system is a reusable JSON-Schema form component, not a training-only widget

## Approval Gate to Enter L3

L3 should proceed only if this L2 design is accepted:

- v3 storage adds `trained_model` and `work_item.best_trained_model_id`
- task execution is sequentially queued in v1
- task-local dataset copies replace the shared dataset temp-copy area for ML execution
- best-model updates are governed by explicit evaluation policies
- the initial model set is supervised-first, while the contracts still allow targetless models later
