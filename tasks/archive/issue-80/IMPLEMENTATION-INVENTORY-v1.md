# Issue 80 - Implementation Inventory v1

## Purpose

This document replaces the need for an `L3` plan.

It lists only:

1. the task-local plans still needed during implementation,
2. the concrete files that are likely necessary to change or add,
3. the minimum test surfaces that should move with the implementation.

## Plans Still Needed

Implementation should use only these task-local planning documents as active references:

1. `tasks/issue-80/ISSUE-80-DESCRIPTION-v1.md`

- product scope and acceptance criteria

2. `tasks/issue-80/L2-PLAN.md`

- approved low-level architecture and scope boundaries

3. `tasks/issue-80/L2-UX-ADAPTATION-PLAN.md`

- non-technical-user UX behavior and reuse/adaptation constraints

## Plans No Longer Needed For Active Coding

These remain useful as historical context, but implementation should not treat them as active specs:

1. `tasks/issue-80/L0-PLAN.md`
2. `tasks/issue-80/L1-PLAN.md`
3. `tasks/issue-80/PLAN-REVIEW-v1.md`

## Existing Files Likely Necessary To Edit

## App Composition

1. `src/xenix/app.py`

- wire new scenario services and new home/history/settings UI surfaces into app composition

2. `src/xenix/ui/main_window.py`

- replace tab-first shell with scenario-first home shell
- route to Window A / B / C
- move language/runtime controls into Settings dialog
- expose History entry from Home

## Existing Workspace Refactor Surfaces

3. `src/xenix/ui/dataset_workspace.py`

- extract reusable dataset inspection and work-item creation behavior for Window A

4. `src/xenix/ui/ml_workspace.py`

- extract reusable training runtime panel behavior for Window B

5. `src/xenix/ui/inference_workspace.py`

- extract reusable inference runtime and result actions for Window C and History

## Existing Widgets Likely Necessary To Edit

6. `src/xenix/ui/widgets/file_drop_zone.py`

- scenario-specific guidance and friendlier upload affordances

7. `src/xenix/ui/widgets/dataset_summary.py`

- friendlier default summary and advanced-details collapse

8. `src/xenix/ui/widgets/column_selection.py`

- guided target/input flow and plain-language labels

9. `src/xenix/ui/widgets/inference_row_editor.py`

- scenario-mode form-first experience for single prediction

10. `src/xenix/ui/widgets/task_log_view.py`

- plain-language status layer above raw logs

## Existing Service Files That May Need Small Integration Changes

These should stay stable if possible, but are legitimate touch points if the implementation needs small integration helpers.

11. `src/xenix/services/project_service.py`

- only if a helper for resolving the hidden scenario project is placed here

12. `src/xenix/services/ml_service.py`

- only if Window B needs a small workflow-facing helper beyond current fit/tune/infer APIs

## New Files Worth Creating

Prefer adding focused new files instead of overloading the old workspaces.

## New Services

1. `src/xenix/services/scenario_template_service.py`

- owns fixed v1 scenario template definitions

2. `src/xenix/services/scenario_workflow_service.py`

- owns hidden scenario-project resolution
- owns ordered training-plan submission
- owns run-state aggregation for Window B

3. `src/xenix/services/inference_history_service.py`

- owns inference-result-centric history query and shaping

## New UI Surfaces

4. `src/xenix/ui/scenario_home_view.py`

- scenario cards, Settings entry, History entry

5. `src/xenix/ui/settings_dialog.py`

- language and runtime-path/log controls moved out of the main surface

6. `src/xenix/ui/inference_history_dialog.py`

- inference-result list, time filter, open/export actions

7. `src/xenix/ui/scenario_data_preparation_dialog.py`

- Window A composition around dataset import and guided column selection

8. `src/xenix/ui/scenario_training_dialog.py`

- Window B composition around ordered-plan training progress

9. `src/xenix/ui/scenario_inference_dialog.py`

- Window C composition around best-model inference flow

## Optional Shared UI Extraction Files

Only create these if extraction from old workspaces is cleaner than embedding logic directly in the new dialogs.

10. `src/xenix/ui/panels/data_preparation_panel.py`
11. `src/xenix/ui/panels/training_runtime_panel.py`
12. `src/xenix/ui/panels/inference_runtime_panel.py`

## Files That Should Not Be Part Of Issue 80

Do not plan implementation around these for `#80`:

1. `src/xenix/services/ml_task_service.py`

- no dispatcher-pool or bounded-parallel rewrite in this issue

2. `src/xenix/services/ml/contracts.py`

- no persisted scenario metadata contract change is required for v1

3. `src/xenix/services/work_item_service.py`

- keep ownership boundaries intact; pass hidden scenario `project_id` from orchestration instead of changing ownership

4. legacy `ml/` scripts

- explicitly out of scope

## Minimum Test Files To Add Or Update

## Existing Tests Likely To Update

1. `tests/test_main.py`

- main-window startup and new home shell

2. `tests/test_i18n.py`

- language switching still updates the new main surfaces without breaking state

## New Tests Worth Adding

3. `tests/test_scenario_workflow.py`

- hidden scenario-project resolution
- fixed ordered training-plan submission
- proceed-to-C gate using `best_trained_model_id`

4. `tests/test_inference_history.py`

- inference-result filtering, sorting, and persisted-output inclusion

5. `tests/test_scenario_ui.py`

- Home -> A -> B -> C wiring at the UI-contract level
- default path hides project and manual technical controls

## Suggested Implementation Order

1. `src/xenix/services/scenario_template_service.py`
2. `src/xenix/services/scenario_workflow_service.py`
3. `src/xenix/services/inference_history_service.py`
4. `src/xenix/ui/main_window.py`
5. `src/xenix/ui/scenario_home_view.py`
6. `src/xenix/ui/scenario_data_preparation_dialog.py`
7. `src/xenix/ui/scenario_training_dialog.py`
8. `src/xenix/ui/scenario_inference_dialog.py`
9. `src/xenix/ui/inference_history_dialog.py`
10. widget refinements and test updates

## Implementation Reading Order

Before coding, the minimum reading set is:

1. `tasks/issue-80/ISSUE-80-DESCRIPTION-v1.md`
2. `tasks/issue-80/L2-PLAN.md`
3. `tasks/issue-80/L2-UX-ADAPTATION-PLAN.md`
4. `src/xenix/app.py`
5. `src/xenix/ui/main_window.py`
6. `src/xenix/ui/dataset_workspace.py`
7. `src/xenix/ui/ml_workspace.py`
8. `src/xenix/ui/inference_workspace.py`
