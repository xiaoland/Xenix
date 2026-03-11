# L1 Plan

## Stage Goal

Define the high-level strategy for issue `#73` using the approved L0 analysis and the GitHub review comments on commit `fa0d7adbdaba182b2689c141e37e3554aa670bd1`.

This stage is intentionally split into smaller review files. `L1-PLAN.md` is the index and decision summary. The detailed strategy lives in the sub-plan files below.

Issue `#73` is downstream of:

- issue `#72` for trained-model persistence, best-model tracking, and background ML task execution
- issue `#75` for dataset inspection, file-format support, and dataset/work-item setup UI patterns

## Review Map

- `L1-PLAN-01-ARCHITECTURE.md`
  - scope boundary
  - product flow
  - service and execution topology
- `L1-PLAN-02-DATA-LIFECYCLE.md`
  - work-item immutability strategy
  - dataset reuse strategy for inference outputs
  - task/input/result ownership
- `L1-PLAN-03-UI-DELIVERY.md`
  - workspace strategy
  - manual-entry widget direction
  - open/export behavior
  - testing and documentation strategy

## L1 Decisions

The revised L1 locks these high-level decisions:

- inference remains inside the existing `MLService` / `MLTaskService` boundary instead of introducing a second workflow service stack
- inference uses one file-based execution contract:
  - batch inference passes user-selected files
  - manual entry is serialized into a service-owned temporary CSV before task submission
- the app should default inference model selection from `work_item.best_trained_model_id`, but still allow switching to any other trained model on the same work item
- work items should become dataset-bound and feature-bound at creation time, and that binding should be immutable after creation
- app-managed dataset copying should move from ML-task dispatch time to work-item attachment time
- inference should reuse `dataset` for persisted tabular prediction outputs, with reverse linkage through nullable `dataset.ml_task_id`
- inference-specific lineage and execution metadata remain task-owned in `ml_task.request_payload`, `ml_task.result_payload`, and task artifacts
- manual inference input requires a dedicated row-entry widget rather than stretching the generic JSON-schema form
- canonical inference result artifacts remain app-owned; `Export` copies them to a user-chosen destination
- arbitrary external model-file loading stays out of scope; inference loads only locally registered trained models

## Approval Gate To Enter L2

L2 should proceed only if this L1 direction is accepted:

- keep inference on the current native ML service and task-execution stack
- make work-item dataset/feature binding immutable through the work-item creation flow
- normalize both manual and batch inference into one file-based execution contract
- reuse `dataset` for persisted tabular inference outputs instead of creating a separate inference-result catalog
- keep inference lineage metadata task-owned rather than duplicating it across new persistence tables
- use a dedicated table-style row-entry widget for manual prediction input
- treat canonical result files as app-managed artifacts and implement export as copy
