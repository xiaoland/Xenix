# L2 Plan

## Stage Goal

Define the concrete low-level design for issue `#73`: schema changes, dataset provenance rules, service APIs, inference request/result contracts, worker execution flow, UI modules, and test boundaries.

This stage is split into focused files so the review can happen by concern rather than through one oversized document.

## Review Map

- `L2-PLAN-01-DOMAIN-STORAGE.md`
  - schema `v4`
  - dataset provenance fields
  - work-item-owned dataset copies
  - runtime layout
- `L2-PLAN-02-SERVICES-EXECUTION.md`
  - public service APIs
  - work-item creation algorithm
  - inference submission and finalization flow
- `L2-PLAN-03-INFERENCE-CONTRACTS.md`
  - Pydantic request/result models
  - model-service inference API
  - input and output file rules
- `L2-PLAN-04-UI-TESTING.md`
  - inference workspace
  - row-entry widget
  - test and documentation boundaries

## L2 Decisions

This L2 draft locks the following concrete choices:

- schema version advances from `3` to `4`
- `dataset` becomes the single persisted tabular-file registration model for:
  - user-managed source datasets
  - work-item-managed copied datasets
  - generated inference output datasets
- `DatasetRow` gains:
  - `copied_from: str | None`
  - `copied_at: datetime | None`
  - `ml_task_id: str | None`
- `work_item.dataset_id` becomes non-nullable and points to the copied dataset row owned by that work item
- work-item creation replaces `attach_dataset_selection(...)` as the only forward path for dataset/feature binding
- no backward-compatibility migration is required for local MVP development:
  - fresh schema `v4` is supported directly
  - older local databases should trigger a clear reset-required error rather than an automatic destructive migration
- `MLService` exposes one file-based inference workflow method:
  - `infer(input_data: InferWithFilesInput)`
- manual entry remains a UI feature, but it is normalized into a temporary CSV by the dataset domain before inference submission
- canonical inference outputs are always written as CSV for v1 simplicity
- each successful inference task produces:
  - one canonical CSV artifact under `artifacts/inference/`
  - one generated `dataset` row linked by `dataset.ml_task_id`
  - one `MLTaskArtifactKind.INFERENCE_RESULT`
- inference extends the current `MLTaskService` queue and worker-process runtime rather than creating a separate execution stack
- model services gain an explicit `infer(...)` operation alongside `fit(...)`, `tune(...)`, and `evaluate(...)`

## Approval Gate To Enter L3

L3 should proceed only if this L2 design is accepted:

- v4 storage redefines `dataset` as the persisted tabular-asset registry with provenance fields
- `work_item.dataset_id` points to a copied dataset row, not the original external dataset row
- old local databases are reset manually instead of being auto-migrated destructively
- inference submission is file-based end to end, with manual entry materialized to temporary CSV before calling `MLService.infer(...)`
- inference output is canonicalized to one CSV artifact and one generated dataset row per task
- `MLTaskService` remains the atomic task runtime and learns how to finalize `INFERENCE`
