# Data Cleaning Handoff

## Purpose

This file hands off the Native AI First branch to the next thread focused on data cleaning.

The current branch state is ChatBox-first. The app starts into a History sidebar plus `ThreadDetailView`; user interaction flows through `AgentHarnessService`, persisted threads/turns/messages, static tool specs, and service-owned artifacts.

## Current Architecture State

- Runtime composition starts in `src/xenix/app.py`.
- `MainWindow` in `src/xenix/ui/main_window.py` owns only the ChatBox shell, Settings entry, History sidebar, Agent Harness events, and `artifact://` link opening.
- Agent Harness lives under `src/xenix/services/agent/`.
- Tool definitions and handlers live in `src/xenix/services/agent/tools.py`.
- Dataset registration/inspection/export remains in `src/xenix/services/dataset_service.py` and `src/xenix/services/dataset_inspection.py`.
- ML execution entrypoint is `src/xenix/services/ml_service.py`.
- ML task queue/worker/artifact persistence is `src/xenix/services/ml_task_service.py`.
- Generic artifact link registration/resolution is `src/xenix/services/artifact_service.py`.

## Retired Paths

- Old scenario Qt screens have exited source composition.
- `WorkItemService` has exited source composition.
- `ScenarioWorkflowService` has exited source composition.
- Inference history dialog/service has exited source composition.
- Storage migrations were reset before production release. Fresh schema has no WorkItem table/columns. Existing local development DBs from the prior baseline should be deleted and rebuilt.

## Data Cleaning Tool Contract

Current first-slice tool:

```text
data.clean(
  dataset_id: string,
  name?: string,
  drop_duplicates?: boolean
) -> cleaned dataset artifact
```

Current behavior:

- Loads the dataset through `DatasetService`.
- Drops duplicate rows by default.
- Fills missing numeric values with median.
- Fills missing non-numeric values with mode, falling back to an empty string.
- Writes a generated CSV under `artifacts/datasets/cleaned/`.
- Registers the generated dataset and a generic `ArtifactKind.DATASET` artifact.
- Returns `dataset_id`, `artifact_id`, `artifact_link`, and inspection payload.

## Recommended Next Slice

Focus the next thread on improving `data.clean` while preserving the existing Agent Harness and artifact contracts.

Suggested order:

1. Define a richer but still minimal `data.clean` input schema.
2. Add a service-owned cleaning planner/executor boundary outside UI code.
3. Keep all output discoverable through dataset records and `artifact://` links.
4. Add integration tests at the tool boundary and dataset service boundary.
5. Add an AIMock fixture only after the deterministic tool tests are stable.

## Design Constraints To Preserve

- UI code must not parse CSV/XLSX for business logic.
- Tool handlers can call services, but domain behavior should live in services when it grows beyond orchestration.
- First-slice working state is represented by messages, tool results, and artifacts.
- No structured thread state for derived dataset, feature selection, best model, or prediction refs in this slice.
- `data.transform` / DuckDB DSL remains deferred.
- Artifact links remain the unified result presentation contract.

## Likely Implementation Files

- `src/xenix/services/agent/tools.py`
- `src/xenix/services/dataset_service.py`
- `src/xenix/services/dataset_inspection.py`
- `tests/test_agent_harness_first_slice.py`
- `tests/test_services.py`
- A new focused test file such as `tests/test_data_cleaning.py`

## Verification Baseline

Recent targeted checks for the cleanup slice:

```text
pdm run python -m compileall src tests
pdm run pytest tests/test_main.py tests/test_i18n.py tests/test_services.py tests/test_repositories.py tests/test_agent_harness_first_slice.py -q
pdm run pytest tests/test_ml_execution.py -q
pdm run pytest
```

Storage-reset cleanup baseline full-suite result: `70 passed in 71.46s`.
