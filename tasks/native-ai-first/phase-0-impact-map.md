# Phase 0 Impact Map

## Status

- Mode: Execute.
- Scope: alignment, impact map, and Phase 6 cleanup evidence.
- Date: 2026-05-12.

## Phase 0 Objective

Make durable docs, local rules, and task packet truth coherent for the AI-first branch before mutation-heavy implementation.

## Confirmed Target

- ChatBox is the primary native operator surface.
- Agent Harness is a service under `src/xenix/services/agent/`.
- Agent Harness owns Thread, Turn, Message, tool-call, tool-result, provider interaction, tool execution, cancellation, and run recording.
- Storage provides standardized persistence interfaces for Agent Harness and other services.
- LLM planning and tool ordering remain model-owned.
- First slice uses messages, tool results, and artifacts as the working record.
- First slice excludes structured domain state for derived dataset, feature selection, best model, and prediction refs.
- First slice excludes `data_transform`.
- Old scenario UI, `ScenarioWorkflowService`, `WorkItemService`, and WorkItem ownership exit the target topology.

## Durable Docs Updated

- `docs/10-prd/product-scope.md`: primary operator path moved to ChatBox and Agent Harness tools.
- `docs/10-prd/glossary.md`: added ChatBox, Agent Harness, Thread, Turn, Message, Tool result, Artifact, and legacy Work item terms.
- `docs/20-product-tdd/runtime-boundaries.md`: added Agent Harness service boundary and storage-interface ownership rule.
- `docs/20-product-tdd/storage-ownership.md`: moved conversation and artifact metadata into service-owned records persisted through storage interfaces.
- `docs/20-product-tdd/ml-task-lifecycle.md`: changed ML task ownership from work-item inputs to explicit service inputs and artifact metadata.
- `docs/40-deployment/development.md`: startup expectation moved to ChatBox-first shell.
- `docs/40-deployment/runtime-state.md`: runtime artifact layout moved away from work-item-specific directories.

## Local Rules Updated

- `src/xenix/ui/AGENTS.md`: ChatBox-first UI guidance replaces scenario-first guidance.
- `src/xenix/ui/widgets/AGENTS.md`: shared widget guidance now avoids old scenario assumptions.
- `src/xenix/services/AGENTS.md`: service layer guidance now names Agent Harness and artifact/data/ML boundaries.
- `src/xenix/services/ml/AGENTS.md`: ML guidance now targets explicit service inputs and service-managed model artifacts.

## Active Code Impact

### Composition Root

- `src/xenix/app.py`
  - Constructs Agent Harness, artifact/data/ML services, provider config, and ChatBox shell.

### UI Active Path

- `src/xenix/ui/main_window.py`
  - Hosts ChatBox, Settings, History sidebar, artifact link opening, and Agent Harness event handling.

### Old UI Surfaces

Target removal or rewrite candidates:

- `src/xenix/ui/scenario_home_view.py`
- `src/xenix/ui/scenario_data_preparation_dialog.py`
- `src/xenix/ui/scenario_model_source_dialog.py`
- `src/xenix/ui/scenario_training_selection_dialog.py`
- `src/xenix/ui/scenario_training_dialog.py`
- `src/xenix/ui/scenario_inference_dialog.py`
- `src/xenix/ui/dataset_workspace.py`
- `src/xenix/ui/ml_workspace.py`
- `src/xenix/ui/inference_workspace.py`
- `src/xenix/ui/inference_history_dialog.py`

Reusable UI behavior preserved or moved forward:

- Dataset preview presentation patterns.
- Long-running task progress rendering patterns.
- Artifact/file opening affordances after service path resolution.
- Existing i18n discipline through `retranslate_ui()` and `QEvent.LanguageChange`.

Cleanup result:

- Old scenario/workspace Qt modules have exited source composition.

### Service Layer

Target removal or rewrite candidates:

- `src/xenix/services/work_item_service.py`
- `src/xenix/services/scenario_workflow_service.py`
- `src/xenix/services/scenario_model_source_service.py`
- `src/xenix/services/scenario_training_preset_service.py`
- `src/xenix/services/scenario_template_service.py`
- `src/xenix/services/analysis_scenario_service.py`

Reusable service behavior to preserve:

- `DatasetService` source registration, source inspection, and export helpers.
- `dataset_inspection.py` CSV/XLSX inspection and dataframe loading utilities.
- `MLTaskService` queueing, worker dispatch, status, logs, and task artifact handling.
- `services/ml/` model registry, model services, evaluation policy, and execution operations.
- Prediction result browsing now flows through artifacts and ChatBox links.

Cleanup result:

- `WorkItemService`, `ScenarioWorkflowService`, scenario support services, and inference history service have exited source composition.

### Storage Layer

Target refactor candidates:

- `src/xenix/services/storage/models.py`
  - uses the AI-first baseline without WorkItem rows or work-item-linked ML task/model columns.
- `src/xenix/services/storage/repositories/work_items.py`
  - exited source composition.
- `src/xenix/services/storage/repositories/ml_tasks.py`
  - lists tasks by dataset for active service paths.
- `src/xenix/services/storage/repositories/trained_models.py`
  - lists models by dataset for active service paths.
- `src/xenix/services/storage/layout.py`
  - uses dataset-scoped model and inference directories for active service paths.
- `src/xenix/services/storage/migrations.py`
  - reset to development baseline v1 before production release.

New persistence interfaces needed:

- Agent Harness records: Thread, Turn, Message, tool-call, tool-result, run records.
- Artifact records: kind, title, path, mime/preview metadata, ownership refs.
- ML task records using explicit task input ownership rather than work-item ownership.
- Fresh schema contains no `work_item` table and no `work_item_id` columns.

### ML Layer

Target refactor candidates:

- `src/xenix/services/ml_service.py`
  - public inputs use dataset id, feature columns, target columns, model selections, trained model id, and input files.
- `src/xenix/services/ml_task_service.py`
  - task creation and canonical artifact copying use dataset ids for active paths.
- `src/xenix/services/trained_model_metadata.py`
  - metadata uses source run naming and source dataset fields.

Reusable ML behavior to preserve:

- Model catalog and parameter validation.
- Fit, hyperparameter tuning, evaluation, and inference operation implementations.
- Spawn-compatible worker execution.
- Evaluation metric policy remains; best-candidate comparison is deferred until a dataset/thread-level model selection contract exists.

## Test Impact

Target rewrite groups:

- Scenario UI/workflow tests exited with the retired source modules.
- `tests/test_i18n.py` now covers ChatBox shell translation.
- `tests/test_services.py` now covers data service and dataset-scoped ML task state transitions.
- `tests/test_repositories.py` now covers dataset-scoped task/model repositories plus migrations.
- `tests/test_ml_execution.py` now uses explicit dataset-scoped ML service inputs.

Reusable test ideas:

- Dataset inspection and validation fixtures.
- ML execution fixture datasets and task completion polling.
- Storage bootstrap/runtime isolation helpers.
- Qt translation and smoke-test patterns.

## Phase 0 Exit State

- Durable docs now name ChatBox and Agent Harness as the target direction.
- Local AGENTS rules now match AI-first ownership.
- Impact areas are mapped for app composition, UI, services, storage, ML, and tests.
- Phase 6 cleanup removed old composition paths and old service modules while preserving historical storage compatibility.
