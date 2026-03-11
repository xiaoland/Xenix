# ML Service Guidance

## Scope

This guidance applies to the native ML workflow under `src/xenix/services/ml/`, `src/xenix/services/ml_service.py`, and `src/xenix/services/ml_task_service.py`.

## Boundaries

- `MLService` is the workflow-facing boundary used by the UI.
- `MLTaskService` owns atomic task queueing, worker dispatch, task completion/failure, and task artifact registration.
- `MLWorkerRunner` is only a process helper. It must not own ML task lifecycle or workflow branching.
- `DatasetService` keeps dataset inspection ownership. ML code may consume inspection results, but it must not re-own dataset analysis.
- `WorkItem` remains the persistence owner for dataset linkage plus feature/target selection.

## Execution Rules

- Each persisted `MLTask` is one model and one operation.
- Issue `#72` supports `fit`, `hyperparameter_tuning`, and `evaluate`.
- `fit` and `hyperparameter_tuning` may request workflow-owned follow-up `evaluate` tasks through `MLService`.
- Sequential execution is intentional in v1: only one worker process runs at a time.
- Use `multiprocessing` with `spawn`-compatible top-level entrypoints so the packaged app does not depend on an external Python CLI.

## Storage Rules

- SQLite stores task metadata, task status, request/result payloads, and trained-model registration rows.
- Worker-owned execution files stay under `artifacts/ml-tasks/<ml-task-id>/`.
- Canonical trained model files stay under `artifacts/models/<work-item-id>/`.
- Dataset source files stay external and user-managed.
- Dataset inspection metadata remains ephemeral and must not be persisted as ML-owned state.

## Model Rules

- Implement native model services under `src/xenix/services/ml/`; do not mutate the legacy `ml/` scripts.
- Registry entries should be Pydantic-driven so the UI can render parameter forms from JSON Schema.
- Keep parameter schemas shallow and predictable. Avoid nested object trees unless the UI contract explicitly grows to support them.
- Evaluation policy ownership belongs in `src/xenix/services/ml/evaluation.py`.
