# Issue 80 - L2 Low-Level Design

## Goal

Define an execution-safe low-level design for issue `#80` that matches the current architecture rather than assuming new scheduler capabilities.

This stage remains design-only. No production code changes are included here.

## Confirmed Scope Decisions

1. Home is scenario-template-first. Technical tabs are not the primary UX.
2. Guided user journey is Window A -> Window B -> Window C.
3. Scenario templates are fixed in v1.
4. Project is invisible in scenario mode.
5. Window B uses a fixed, non-editable training plan in v1.
6. History is an inference-result list aggregated by inference task.
7. Scenario metadata in history is optional in v1.
8. ML parallel execution is in scope for `#80` only if the current architecture already supports it.

## Current Architecture Facts That Constrain L2

1. `WorkItemService.create_work_item(...)` requires a `project_id`.
2. Dataset registration, work-item creation, training, and inference are all project-centric today.
3. `MLTaskService` currently runs one queue with one dispatcher thread.
4. Local ML guidance explicitly treats sequential execution as intentional in the current architecture.
5. `MLService.fit_with_evaluate(...)` and `MLService.tune_with_evaluate(...)` already provide the needed training-to-evaluate continuation path.
6. `MLService.infer(...)` already persists inference results and canonical output paths needed for history.

## L2 Design Result

Based on the current codebase, issue `#80` v1 should:

1. implement the scenario-first UX shell,
2. orchestrate fixed training plans on top of the existing sequential task runner,
3. avoid scheduler re-architecture inside this issue,
4. keep scenario metadata optional and non-blocking for history.

## Invariants

1. Preserve service ownership boundaries:
   - `WorkItemService` owns dataset linkage and feature/target persistence on `WorkItem`.
   - `MLService` remains the UI-facing workflow boundary for training and inference.
   - `MLTaskService` remains the owner of task lifecycle and dispatch.
2. Preserve best-model decision logic in evaluation-policy comparison.
3. Preserve the current continuation rule: each evaluate task starts only after its source training task succeeds.
4. Keep persisted runtime data backward-compatible.
5. Reuse is fit-for-purpose, not mandatory:
   - reuse existing widgets and panels when they help,
   - replace legacy UI when forced reuse harms non-technical clarity.
6. Issue `#80` must not add new business capabilities:
   - no automatic column recommendation,
   - no new business-level training summary service,
   - no new user-editable training pipeline builder.

## v1 Scenario Template Contracts

## Template Keys

- `sales_demand_forecast.v1`
- `customer_outcome_classification.v1`

## Data Types

```python
class TrainingPlanStep(SQLModel):
    step_key: str
    operation: Literal["fit", "hyperparameter_tuning"]
    model_key: str
    params: dict[str, Any] = {}
    param_grid: dict[str, list[Any]] = {}


class ScenarioTemplate(SQLModel):
    key: str
    display_name: str
    description: str
    supervised_required: bool
    min_feature_columns: int
    required_target_count: int
    training_plan: list[TrainingPlanStep]
```

Reasoning:

- `training_plan` is an ordered list, not a parallel branch graph.
- This matches the current sequential scheduler and keeps `#80` implementation-bounded.

## Fixed Template Definitions

1. `sales_demand_forecast.v1`

- Step A: `fit` -> `regression.linear`
- Step B: `hyperparameter_tuning` -> `regression.ridge`
- Step C: `hyperparameter_tuning` -> `regression.random_forest`

2. `customer_outcome_classification.v1`

- Step A: `hyperparameter_tuning` -> `classification.logistic_regression`
- Step B: `hyperparameter_tuning` -> `classification.random_forest`

## Hidden Project Strategy

Scenario mode must not expose project selection, but the current service layer requires `project_id`.

The lowest-risk v1 strategy is:

1. introduce one application-managed scenario project container,
2. create it lazily on first scenario use if it does not already exist,
3. route all scenario-created datasets and work items into that hidden project,
4. keep project completely invisible in Home, A, B, and C.

Implications:

1. The scenario UX remains clean for non-technical users.
2. Existing services can be reused without changing ownership boundaries.
3. Existing persisted projects remain readable and backward-compatible.
4. Old technical views, if kept temporarily during transition, may still expose project-level access for legacy data inspection.

Non-goal for `#80`:

- introducing a new persisted top-level entity to replace `Project`.

## UI Components and Contracts

Detailed adaptation tactics remain in `L2-UX-ADAPTATION-PLAN.md`.
This document defines structural composition and runtime contracts.

## Fit-for-Purpose UI Composition

1. `ScenarioHomeView`

- Responsibility:
  - show scenario cards,
  - open Settings,
  - open History.
- Emits:
  - `scenario_selected(template_key)`
  - `open_settings_requested()`
  - `open_history_requested()`

2. `DataPreparationDialog` (Window A)

- Inputs:
  - selected template definition
- Preferred reuse:
  - `FileDropZone`
  - `DatasetSummaryWidget`
  - `ColumnSelectionWidget`
  - dataset inspection and work-item creation behavior from `DatasetWorkspace`
- Scenario-mode adaptations:
  - hide project selector
  - hide manual work-item naming unless needed as a fallback
  - resolve hidden scenario project automatically
  - enforce template-specific feature/target rules before continue
- Output:
  - `DataPreparationResult(project_id, work_item_id, dataset_id, feature_columns, target_columns)`

3. `TrainingDashboardDialog` (Window B)

- Inputs:
  - template definition
  - `DataPreparationResult`
  - runtime scenario session
- Preferred reuse:
  - task table rendering from `MLWorkspace`
  - trained-model list rendering from `MLWorkspace`
  - task details panel and `TaskLogView`
  - existing translation/status/task-type helpers
- Scenario-mode adaptations:
  - hide manual fit editor
  - hide tuning-grid editor
  - replace manual submit surfaces with one action: `Run Full Plan Again`
  - present progress against the fixed ordered plan, backed by existing task rows
- Output:
  - `proceed_to_inference(work_item_id)`

4. `InferenceDialog` (Window C)

- Inputs:
  - `work_item_id`
  - scenario session context
- Preferred reuse:
  - `InferenceRowEditorWidget`
  - manual and batch input modes
  - inference task table and details panel
  - open/export result actions
- Scenario-mode adaptations:
  - hide project selector
  - hide work-item selector
  - default model to `best_trained_model_id`
  - hide model selector in the default path
- Output:
  - `inference_completed(task_id)`

5. `InferenceHistoryDialog`

- Behavior:
  - list inference results by inference task
  - sort by `finished_at` asc or desc
  - filter by time range
  - open/export result
- Reuse source:
  - inference task row rendering and open/export interactions from `InferenceWorkspace`
  - `TaskLogView` for task details when needed
- v1 rule:
  - do not depend on persisted scenario metadata to render a valid row

6. `SettingsDialog`

- v1 scope:
  - language preference
  - runtime path visibility
  - open-log-directory action
- Reuse source:
  - language switching flow from `MainWindow` and `TranslationManager`
  - runtime path/log open behavior from `MainWindow`

## Extraction Targets

To avoid duplicated UI logic, extract only the seams that are low-risk and obviously reusable:

1. Dataset import and column-selection panel from `DatasetWorkspace`
2. Training runtime panel from `MLWorkspace`
   - task table
   - trained-model list
   - task details and logs
3. Inference runtime panel from `InferenceWorkspace`
   - manual or batch input
   - task table
   - result open/export actions

Extraction rule:

1. prefer widget/panel extraction when state coupling is low,
2. replace dialog-level workflow composition when reuse would keep technical selectors visible,
3. preserve the same service boundaries in both cases.

## Session and State Model

## Runtime Session Model

```python
class ScenarioSession(SQLModel):
    session_id: str
    template_key: str
    project_id: str
    work_item_id: str | None
    dataset_id: str | None
    state: Literal[
        "home",
        "window_a",
        "window_b",
        "window_c",
        "completed",
        "failed",
        "cancelled",
    ]
    active_training_run: list[str] = []
```

Notes:

1. This is a runtime UI orchestration model, not a new persisted storage entity.
2. `active_training_run` stores the root training task ids submitted for the current run.
3. v1 does not require restoring scenario-session state across app restart.

## Transition Rules

1. `home -> window_a`

- trigger: scenario card selected

2. `window_a -> window_b`

- guard:
  - hidden scenario project resolved successfully
  - work item created successfully
  - template column constraints satisfied

3. `window_b -> window_b` rerun

- trigger: `Run Full Plan Again`
- effect:
  - submit the same ordered training plan again
  - replace `active_training_run` with the new root training task ids

4. `window_b -> window_c`

- guard:
  - all tasks in the current training run reached terminal state through their continuation chain
  - `work_item.best_trained_model_id` is not null

5. `window_c -> completed`

- trigger:
  - at least one inference task finished with persisted output

6. `any -> failed`

- trigger:
  - unrecoverable create, submit, or load error

## Sequential Training Orchestration Design

Issue `#80` does not re-architect `MLTaskService` dispatch.

## What Remains Unchanged

1. `MLTaskService` keeps one queue and one dispatcher thread.
2. Each persisted `MLTask` remains one model and one operation.
3. Evaluate continues to be submitted by `MLService` only after its source training task succeeds.

## Scenario Training Submission Algorithm

For each step in `template.training_plan`, submit one root task using the existing `MLService` API:

- `fit_with_evaluate(...)` for `fit`
- `tune_with_evaluate(...)` for `hyperparameter_tuning`

Because the current dispatcher is sequential, runtime behavior becomes:

1. root training task A runs
2. evaluate task A follows on success
3. root training task B runs
4. evaluate task B follows on success
5. continue until the fixed ordered plan completes

This is slower than bounded parallel execution, but it is architecture-safe for `#80`.

## Training Run Completion Rules

For each root task in `active_training_run`:

1. if the root task failed or was cancelled, that plan step failed
2. if the root task succeeded but its follow-up evaluate is still pending or running, that plan step is still running
3. if the follow-up evaluate succeeded, that plan step succeeded
4. if the follow-up evaluate failed or was cancelled, that plan step failed

The current run is terminal when every plan step is terminal.

Proceed-to-C remains enabled only when:

1. the run is terminal, and
2. `best_trained_model_id` exists on the work item

## Optional Scenario Metadata

Scenario metadata is optional in v1 history, so `#80` does not require adding persisted workflow metadata to ML task request contracts.

Allowed v1 stance:

1. scenario flow may keep template identity in runtime UI state only
2. history remains valid without template labels
3. persisted template metadata can be added later if history enrichment becomes necessary

Non-goal for `#80`:

- changing ML request contracts solely to support history labels

## History Query Design

## Service Contract

```python
class InferenceHistoryFilter(SQLModel):
    start_time: datetime | None
    end_time: datetime | None
    sort_direction: Literal["asc", "desc"]


class InferenceHistoryRow(SQLModel):
    inference_task_id: str
    finished_at: datetime
    work_item_id: str
    work_item_name: str | None
    model_key: str | None
    row_count: int | None
    result_dataset_id: str
    result_path: str
    scenario_template_name: str | None = None
```

```python
class InferenceHistoryService:
    def list_results(self, filter: InferenceHistoryFilter) -> list[InferenceHistoryRow]:
        ...
```

## Repository Query Logic

1. Load tasks where:
   - `task_type == INFERENCE`
   - `status == SUCCEEDED`
   - `finished_at is not null`
2. Apply time-range filter by `finished_at`
3. Parse `result_payload` and keep only rows with persisted outputs:
   - `result_dataset_id` exists
   - `canonical_output_path` exists
4. Join `WorkItem` when available to derive `work_item_name`
5. Sort by `finished_at` in the requested direction
6. If scenario metadata is present in payload in the future, include it opportunistically; do not require it

## Main Composition and Dependency Wiring

`build_main_window` composition will likely add:

1. `ScenarioTemplateRegistryService`
2. `ScenarioWorkflowService`
3. `InferenceHistoryService`
4. hidden scenario project resolver

It should not add:

1. bounded parallel-dispatch configuration for `MLTaskService`
2. new scheduler worker pools

## Delivery Sequence

1. Build the home-first shell
2. Introduce hidden scenario-project resolution
3. Extract or replace Window A components needed for guided dataset preparation
4. Build Window B on top of the existing sequential training workflow
5. Build Window C on top of the existing inference workflow
6. Add inference-result-centric history
7. Move language/runtime controls into Settings
8. Remove or de-emphasize tab-first navigation only after scenario parity is acceptable

## Error Handling Rules

1. Window A validation failures are user-correctable and remain in A
2. Window B plan-step failure does not erase already completed trained models
3. Window B cannot proceed to C when no best model exists
4. Window C inference failure does not end the session; the user can retry
5. History silently excludes malformed legacy rows without persisted outputs

## Testing Design Targets

1. Scenario template registry tests

- validate fixed plan definitions and column constraints

2. Hidden scenario project tests

- lazily create or resolve the invisible scenario project
- verify scenario-created work items are routed into it

3. Training orchestration tests

- submit the ordered plan and verify root-task tracking
- verify each evaluate task follows its source training task
- verify rerun submits the same ordered plan definition

4. History service tests

- task-level filtering and sorting
- persisted-output inclusion only
- no dependency on scenario metadata

5. Window transition tests

- A -> B requires valid dataset and column mapping
- B -> C requires best model

6. UI contract parity tests

- scenario dialogs preserve service ownership boundaries
- scenario mode hides project, manual training, and manual model selectors on the default path

## Explicit Non-Goals for Issue 80 v1

1. ML Task-level bounded parallel execution
2. scheduler-pool changes inside `MLTaskService`
3. persisted scenario metadata for history labeling
4. scenario-session recovery across app restart
5. replacing `Project` as a storage concept

## L2 Approval Checklist

1. Approve the hidden application-managed scenario project strategy
2. Approve ordered sequential training plans for `#80` v1
3. Approve history rows that remain valid without scenario labels
4. Approve proceed-to-C gate requiring `best_trained_model_id`

After approval, proceed to L3 implementation planning.
