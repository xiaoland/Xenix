## 📑 Summary

Redesign the native app UX into a scenario-template-first journey so non-technical users can complete end-to-end data analysis quickly, from data upload to inference result output.

## 🤔 Rationale

The current tab-based workflow (Datasets / Training / Inference) exposes technical ML workflow concepts too early.

Issue #80 changes the default interaction model to guided scenario execution:

- users start from business scenario templates
- system runs fixed auto-training plans with ML Task-level parallel execution
- users proceed through a linear A -> B -> C workflow

## 📏 Specification

1. Home information architecture

- Home only shows:
  - scenario template grid cards
  - Settings entry
  - History entry
- Home no longer exposes technical tabs as the primary interaction model.
- Each card represents a business scenario template, not a raw ML problem category.

1. Scenario templates (v1 fixed)

- v1 provides two built-in scenario templates:
  - Sales Demand Forecast
  - Customer Outcome Classification
- Each template defines:
  - whether supervised learning is required
  - required column-selection rules
  - fixed auto-training plan (models, mode, parameter defaults)
  - ML Task-level parallel policy

- Sales Demand Forecast template:
  - supervised_required: true
  - requires: exactly one target column and at least one feature column
  - auto-training plan (fixed ML Task branches):
    1. Branch A: fit + evaluate -> regression.linear (default params)
    2. Branch B: tuning + evaluate -> regression.ridge (default grid)
    3. Branch C: tuning + evaluate -> regression.random_forest (default grid)

- Customer Outcome Classification template:
  - supervised_required: true
  - requires: exactly one target column and at least one feature column
  - auto-training plan (fixed ML Task branches):
    1. Branch A: tuning + evaluate -> classification.logistic_regression (default grid)
    2. Branch B: tuning + evaluate -> classification.random_forest (default grid)

1. Guided workflow

- Clicking a scenario card starts a guided flow:
  - Window A -> Window B -> Window C

- Window A (data preparation)
  - upload/select dataset
  - inspect columns
  - complete required feature/target mapping based on selected template
  - auto-create WorkItem when validation passes
  - close A and open B

- Window B (training dashboard)
  - automatically execute the selected template's fixed multi-model plan using ML Task-level parallel execution (bounded concurrency)
  - automatically run evaluation and auto-select best model
  - display ML task status, logs, and evaluation summaries
  - provide one-click "Run Full Plan Again"
  - in v1, users cannot edit training plan content
  - close B and open C when user proceeds

- Window C (inference)
  - support manual input and file-upload inference
  - run inference using the selected workflow model (default best model)
  - persist result output and link it to task/work item records

1. History semantics

- History is an inference result list, not a WorkItem list.
- Aggregation unit is inference task.
- WorkItems without inference results are not shown.
- Include inference tasks with persisted outputs.
- Support:
  - time ascending / descending sort
  - time-range filtering

1. Settings window

- Provide a standalone Settings window.
- v1 scope includes:
  - language preference
  - runtime path and log visibility (state/artifacts/database/log path visibility and log-directory open action)

### Acceptance Criteria

- [ ] Home shows only scenario cards, Settings entry, and History entry.
- [ ] Selecting either v1 scenario card opens Window A and starts guided A -> B -> C flow.
- [ ] Window A can create a WorkItem from uploaded data and required column mapping.
- [ ] Window B auto-runs predefined multi-model training plan with ML Task-level parallel execution, auto-runs evaluation, and auto-selects best model.
- [ ] Window B provides "Run Full Plan Again" and does not allow plan editing in v1.
- [ ] Window C supports manual and file-based inference and persists result artifacts.
- [ ] History lists inference results by inference task rather than by WorkItem.
- [ ] History excludes entries without persisted inference outputs.
- [ ] History supports time ascending/descending sort and time-range filter.
- [ ] Settings window is accessible from Home and applies language preference.

## 🚧 Technical Constraints

- [ ] Preserve existing service ownership boundaries:
  - WorkItemService owns dataset linkage and feature/target persistence on WorkItem.
  - MLService remains workflow boundary for training/inference operations.
  - MLTaskService remains owner of task lifecycle and execution state.
- [ ] Reuse is fit-for-purpose, not mandatory: replace legacy UI components when forced reuse harms non-technical-user clarity.
- [ ] UX refactor must not introduce new business capabilities (for example, automatic column recommendation or new training-summary business functions).
- [ ] Training execution uses ML Task-level bounded parallelism (default max concurrency 2, configurable).
- [ ] Preserve dependency ordering within each model branch (train/tune before evaluate).
- [ ] Best-model assignment must continue to use evaluation-policy comparison logic.
- [ ] History source of truth must derive from persisted inference task/result data.

## ⏪ Backward Compatibility

- [ ] Existing storage schema and persisted entities remain readable.
- [ ] Existing projects/workitems/tasks do not require destructive migration.
- [ ] UI interaction model can be replaced, but stored runtime data must remain compatible.

## 🔄 Alternatives Considered

Option A: Keep existing technical tabs and add onboarding hints.

- Rejected because it still forces non-technical users to learn technical concepts first.

Option B: Use a generic wizard without scenario templates.

- Rejected because it weakens mapping between business intent and fixed ML plan presets.

Option C: Add fully configurable training-plan builder in v1.

- Rejected because it increases complexity and conflicts with the non-technical-first objective.

## Resources

- Planning source: tasks/issue-80/L1-PLAN.md
