# Phase 0 Impact Map

## Status

- Mode: Solidify.
- Scope: alignment and impact map before implementation phases.
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
  - Currently constructs `WorkItemService`.
  - Currently constructs `ScenarioWorkflowService`.
  - Currently wires scenario services into `MainWindow`.
  - Target composition constructs Agent Harness, artifact/data/ML services, provider config, and ChatBox shell.

### UI Active Path

- `src/xenix/ui/main_window.py`
  - Currently uses `ScenarioHomeView` as central path.
  - Currently creates dataset, ML, inference workspaces and scenario dialogs.
  - Target `MainWindow` hosts ChatBox and delegates interaction to Agent Harness.

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

Reusable UI behavior to preserve:

- Dataset preview presentation patterns.
- Long-running task progress rendering patterns.
- Artifact/file opening affordances after service path resolution.
- Existing i18n discipline through `retranslate_ui()` and `QEvent.LanguageChange`.

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
- `InferenceHistoryService` result-row building ideas, after artifact ownership is replaced.

### Storage Layer

Target refactor candidates:

- `src/xenix/services/storage/models.py`
  - currently includes WorkItem rows and work-item-linked ML task/model records.
- `src/xenix/services/storage/repositories/work_items.py`
  - exits target topology.
- `src/xenix/services/storage/repositories/ml_tasks.py`
  - currently indexes/list tasks by work item.
- `src/xenix/services/storage/repositories/trained_models.py`
  - currently indexes/list models by work item.
- `src/xenix/services/storage/layout.py`
  - currently includes work-item-specific dataset, model, and inference directories.
- `src/xenix/services/storage/migrations.py`
  - needs migration path for Agent Harness records and artifact metadata.

New persistence interfaces needed:

- Agent Harness records: Thread, Turn, Message, tool-call, tool-result, run records.
- Artifact records: kind, title, path, mime/preview metadata, ownership refs.
- ML task records using explicit task input ownership rather than work-item ownership.

### ML Layer

Target refactor candidates:

- `src/xenix/services/ml_service.py`
  - current public inputs use `work_item_id`.
  - target public inputs use dataset id, feature columns, target columns, model selections, and artifact output owner.
- `src/xenix/services/ml_task_service.py`
  - current task creation and canonical artifact copying use work-item ids.
  - target task creation uses explicit owner/artifact refs and artifact service registration.
- `src/xenix/services/trained_model_metadata.py`
  - current metadata includes source work-item naming.
  - target metadata should use artifact/source dataset/modeling context fields.

Reusable ML behavior to preserve:

- Model catalog and parameter validation.
- Fit, hyperparameter tuning, evaluation, and inference operation implementations.
- Spawn-compatible worker execution.
- Evaluation metric policy and best-candidate comparison logic, adapted to artifact-backed results.

## Test Impact

Target rewrite groups:

- `tests/test_scenario_ui.py`: replace with ChatBox UI and artifact preview tests.
- `tests/test_scenario_workflow.py`: replace with Agent Harness tool and service integration tests.
- `tests/test_i18n.py`: replace scenario dialog expectations with ChatBox/message renderer expectations.
- `tests/test_services.py`: replace WorkItemService tests with data/artifact service tests.
- `tests/test_repositories.py`: replace WorkItem repository tests with Agent Harness and artifact repository tests.
- `tests/test_ml_execution.py`: refactor setup to explicit ML service inputs.
- `tests/test_inference_history.py`: refactor or replace with artifact-backed prediction result browsing.

Reusable test ideas:

- Dataset inspection and validation fixtures.
- ML execution fixture datasets and task completion polling.
- Storage bootstrap/runtime isolation helpers.
- Qt translation and smoke-test patterns.

## Phase 0 Exit State

- Durable docs now name ChatBox and Agent Harness as the target direction.
- Local AGENTS rules now match AI-first ownership.
- Impact areas are mapped for app composition, UI, services, storage, ML, and tests.
- Implementation remains pending until Phase 1 low-level contracts are confirmed.

