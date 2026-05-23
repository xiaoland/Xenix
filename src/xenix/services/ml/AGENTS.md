# ML Service Guidance

## Scope

This guidance applies to the native ML workflow under `src/xenix/services/ml/`, `src/xenix/services/ml_service.py`, and `src/xenix/services/ml_task_service.py`.

## Boundaries

- `MLService` is the service-facing boundary used by Agent Harness tools and other services.
- `MLTaskService` owns atomic task queueing, worker dispatch, task completion/failure, and task artifact registration.
- `MLWorkerRunner` is only a process helper. It must not own ML task lifecycle or workflow branching.
- `DatasetService` keeps dataset inspection ownership. ML code may consume inspection results, but it must not re-own dataset analysis.
- Agent Harness and tool results carry the first-slice working record. Target training and tuning service inputs should reference immutable column role bindings; ML task payloads should expand those references into explicit dataset id, role bindings, model selections, parameters, and artifact output owner.

## Execution Rules

- Each persisted `MLTask` is one model and one operation.
- `fit` and `hyperparameter_tuning` may request workflow-owned follow-up `evaluate` tasks through `MLService`.
- Worker pool dispatch is intentional after issue #94. The default local-only configuration remains conservative, while configured workers may each expose a small number of execution slots. Worker selection is internal service placement, not an Agent tool argument.
- v1 worker pool dispatch does not perform automatic retry, failover, or duplicate execution after a selected worker fails.
- Use `multiprocessing` with `spawn`-compatible top-level entrypoints so the packaged app does not depend on an external Python CLI.
- SSH workers use OpenSSH-style process boundaries, stage task files remotely, and must download outputs back to local task directories before `MLTaskService` finalizes artifacts.

## Storage Rules

- SQLite stores task metadata, task status, request/result payloads, and trained-model registration rows.
- Worker-owned execution files stay under `artifacts/ml-tasks/<ml-task-id>/`.
- Canonical trained model files stay under service-managed model artifact directories.
- Dataset source files stay external and user-managed.
- Dataset inspection metadata remains ephemeral and must not be persisted as ML-owned state.

## Model Rules

- Implement native model services under `src/xenix/services/ml/`; do not mutate the legacy `ml/` scripts.
- Registry entries should be Pydantic-driven so the UI can render parameter forms from JSON Schema.
- Keep parameter schemas shallow and predictable. Avoid nested object trees unless the UI contract explicitly grows to support them.
- Evaluation policy ownership belongs in `src/xenix/services/ml/evaluation.py`.
