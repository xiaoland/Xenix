# Issue 80 - L1 High-Level Strategy

## Stage Goal

Translate confirmed product intent into a stable high-level solution strategy for:

- scenario-template-first UX
- guided A -> B -> C workflow
- standalone settings window
- inference-result-centric history list

This stage still does not include implementation.

## Confirmed Inputs (From Latest Discussion)

1. Home cards represent scenario templates, not ML problem labels.
2. Each scenario template defines:
   - whether supervised learning is required

- fixed auto-training plan (model set, mode, parameters)
- ML Task-level execution policy

1. Window B training behavior is fixed:
   - multi-model auto training

- ML Task-level parallel execution with bounded concurrency
- automatic evaluation
- automatic best-model selection
- no training-plan editing in v1
- only one-click full rerun is allowed

1. History semantics are fixed:
   - history is an inference result list
   - list is aggregated by inference task, not by WorkItem

## Proposed UX Architecture

### 1. Home (single entry surface)

Home includes only:

- scenario card grid
- Settings button
- History button

No technical tabs are shown on Home.

### 2. Scenario Session Orchestration

A selected scenario card starts a guided run:

- Window A: data preparation and optional/required column mapping
- Window B: auto-training dashboard and rerun
- Window C: inference input and execution

The transition is linear by default:
Home -> A -> B -> C -> Home

### 3. Core Orchestrator (high-level responsibility)

Introduce a workflow orchestrator layer in UI/application flow that:

- creates and tracks one active Scenario Session
- maps scenario template to backend operations
- manages window transition gates and validation
- keeps technical entities (project/work item/model IDs) mostly hidden

## Topology (High-Level)

[Home UI]
  -> select scenario template
[Scenario Session Orchestrator]
  -> Window A (dataset + columns)
  -> WorkItemService/DatasetService
  -> Window B (auto-training dashboard)
  -> MLService (fit/tune/evaluate task graph)
  -> best model auto-selected on WorkItem
  -> Window C (inference)
  -> MLService.infer + persisted result dataset/artifact
  -> History view consumes inference task rows

## Execution Strategy (ML Task Parallelism)

1. Parallel unit is ML Task.
2. Scenario plan is represented as multiple model branches:

- branch-internal dependency is preserved (train/tune -> evaluate).
- cross-branch tasks are eligible to run in parallel.

1. Runtime uses bounded concurrency for stability:

- default max concurrent workers: 2
- must be configurable for low-spec devices.

1. "Run Full Plan Again" re-submits the same template task graph with the same parallel policy.
2. Best-model selection remains deterministic and independent from completion order:

- continue using evaluation-policy comparison logic.

## Proposed v1 Scenario Templates (2 cards)

Given current model catalog support (regression.linear, regression.ridge, regression.random_forest, classification.logistic_regression, classification.random_forest), define two practical business templates:

### Scenario 1: Sales Demand Forecast

- Card intent: forecast numeric outcomes such as sales amount, demand volume, next-period quantity.
- supervised_required: true
- target_columns_required: exactly 1
- feature_columns_required: >= 1
- auto-training plan (fixed ML Task branches):
  1. Branch A: fit + evaluate -> regression.linear (default params)
  2. Branch B: hyperparameter tuning + evaluate -> regression.ridge (default grid)
  3. Branch C: hyperparameter tuning + evaluate -> regression.random_forest (default grid)
- best model policy: existing regression default policy
  - primary: r2 (maximize)
  - tie-breakers: rmse, mae

### Scenario 2: Customer Outcome Classification

- Card intent: classify customer outcome such as churn/non-churn, conversion/no-conversion, repayment risk class.
- supervised_required: true
- target_columns_required: exactly 1
- feature_columns_required: >= 1
- auto-training plan (fixed ML Task branches):
  1. Branch A: hyperparameter tuning + evaluate -> classification.logistic_regression (default grid)
  2. Branch B: hyperparameter tuning + evaluate -> classification.random_forest (default grid)
- best model policy: existing classification default policy
  - primary: f1_weighted (maximize)
  - tie-breakers: accuracy, precision_weighted, recall_weighted

Note:

- v1 does not provide unsupervised scenario cards because current native model catalog is supervised-only.
- unsupervised scenarios can be added in later issues without changing this v1 journey contract.

## Window Responsibilities (High-Level)

### Window A - Data Preparation

Responsibilities:

- upload/select one dataset file
- inspect dataset columns
- collect required column mapping according to template
- create WorkItem automatically when validation passes

Rules:

- if supervised_required = true, require feature + target mapping before continue
- if supervised_required = false in future templates, column mapping may be optional

Completion behavior:

- auto-create WorkItem
- close A
- open B

### Window B - Training Dashboard

Responsibilities:

- automatically execute scenario training task graph
- present ML task status timeline
- present logs and evaluation summaries
- indicate currently selected best model

Rules:

- no plan editing in v1
- execute by ML Task-level parallelism with bounded concurrency
- "Run Full Plan Again" reruns the same fixed plan only

Completion behavior:

- user confirms result quality
- close B
- open C

### Window C - Inference

Responsibilities:

- support manual input and file-upload inference
- run inference with selected/best model policy (default best model)
- persist output and link to WorkItem/task artifacts

Completion behavior:

- inference result remains queryable in History list

## History Strategy (Inference Result List)

Data unit:

- one list row per inference task result record

Recommended inclusion rule for v1:

- include succeeded inference tasks that have persisted result dataset/path

Sorting/filtering:

- sort by task finished time asc/desc
- filter by time range [start, end]

History row payload (high-level):

- inference task id
- finished time
- scenario template name
- model key
- row count
- result path or result dataset id

## Settings Strategy (Standalone Window)

v1 scope recommendation:

- language preference
- runtime path visibility (state/artifacts/db/log)
- open-log-directory shortcut

v1 non-goals for settings:

- advanced training-plan editing
- dynamic scenario authoring
- deep runtime path mutation/migration workflow

## Scope and Non-Goals

In scope:

- scenario-first navigation and A/B/C journey
- two built-in scenario templates
- fixed auto-training plan execution (ML Task-level parallel) and rerun
- inference-result-centric history list
- standalone settings window
- reuse existing UI widgets/views with minimal adaptation where feasible

Out of scope for issue 80 v1:

- configurable scenario designer
- unsupervised ML templates
- user-editable training pipelines
- multi-user collaboration

## Risk-Control Strategy

1. Keep backend service boundaries stable (WorkItemService, MLService, MLTaskService).
2. Add orchestration in UI layer and reuse existing workspace widgets/panels before creating new ones.
3. Reuse existing best-model update logic instead of introducing a second selection mechanism.
4. Define clear transition guards between A/B/C to prevent partial or invalid states.

## Candidate Durable Destinations (Later, After Scope Confirmation)

Product truth candidates:

- docs/10-prd/product-scope.md (scenario-first entry, history semantics)

Technical truth candidates:

- docs/30-unit-tdd/* (journey orchestration contracts, state transitions)

Temporary reasoning during refinement:

- tasks/issue-80/*

## Issue 80 Description Draft (v1)

### Summary

Redesign native UX into a scenario-template-first journey so non-technical users can complete end-to-end data analysis tasks quickly, from data upload to inference result export.

### Rationale

Current tab-based technical workflow (datasets/training/inference) requires users to understand ML workflow internals.
Issue 80 changes the default interaction model to guided scenario execution.

### Specification

1. Home

- Home only shows:
  - scenario template grid cards
  - Settings entry
  - History entry
- Cards represent business scenario templates, not raw ML problem categories.

1. Scenario templates (v1 fixed)

- Sales Demand Forecast (supervised)
- Customer Outcome Classification (supervised)
- Each template defines:
  - whether supervised column mapping is required
  - fixed auto-training plan (models, mode, parameters)
  - ML Task-level parallel policy

1. Guided flow

- Card click opens Window A.
- Window A:
  - upload/select dataset
  - perform required column mapping by template
  - auto-create WorkItem on completion
  - close A and open B
- Window B:
  - auto-run fixed multi-model training plan using ML Task-level parallel execution (bounded concurrency)
  - auto-run evaluation
  - auto-select best model
  - display task statuses, logs, and evaluation metrics
  - allow one-click full rerun of same plan
  - disallow training-plan editing in v1
  - user confirms and proceeds
  - close B and open C
- Window C:
  - manual input or file upload for inference
  - run inference and persist result
  - link output to WorkItem/task artifacts

1. History

- History is an inference result list (task-level), not a WorkItem list.
- WorkItems without inference results are not shown.
- Support:
  - time asc/desc sorting
  - time-range filtering

1. Settings

- Provide standalone settings window.
- v1 includes language and runtime path/log visibility controls.

### Acceptance Criteria

- [ ] Home shows only scenario cards, Settings, and History entries.
- [ ] Selecting each v1 scenario card opens Window A and starts guided A -> B -> C flow.
- [ ] Window A can create a WorkItem from uploaded data and required column mapping.
- [ ] Window B automatically executes the predefined multi-model plan with ML Task-level parallel execution, evaluates models, and marks best model.
- [ ] Window B provides "Run Full Plan Again" with no plan-edit capability.
- [ ] Window C supports manual and file-based inference and persists result artifacts.
- [ ] History lists inference results by inference task and excludes non-inference WorkItems.
- [ ] History supports ascending/descending time sorting and time-range filtering.
- [ ] Settings window is accessible from Home and can apply language preference.

### Technical Constraints

- [ ] Preserve existing service boundaries:
  - WorkItemService remains owner of dataset/column linkage on WorkItem.
  - MLService remains workflow boundary for training/inference.
  - MLTaskService remains owner of task lifecycle.
- [ ] Training execution uses ML Task-level bounded parallelism (default max concurrency 2, configurable).
- [ ] Preserve dependency ordering within each model branch (train/tune before evaluate).
- [ ] Persisted best-model update must use existing evaluation-policy comparison logic.
- [ ] Inference history source of truth must derive from persisted inference tasks/results.

### Backward Compatibility

- [ ] Existing storage schema and persisted entities remain readable.
- [ ] Existing technical tabs may be replaced by new flow in UI, but no data migration breakage is allowed for existing projects/workitems/tasks.

### Alternatives Considered

- Option A: Keep tab architecture and add onboarding tooltips.
  - Rejected: still exposes technical concepts too early for non-technical users.

- Option B: Wizard-only flow with no scenario cards.
  - Rejected: loses direct mapping between business intent and model plan presets.

- Option C: Fully configurable training-plan builder in v1.
  - Rejected: too complex for v1 and conflicts with non-technical-first goal.

## Questions For L1 Approval

1. Approve the two proposed v1 scenario cards and fixed model plans?
2. Approve history inclusion rule as "succeeded inference tasks with persisted outputs"?
3. Approve settings v1 scope as language + runtime path/log visibility only?

If approved, proceed to L2 with low-level interfaces, state machine, and API/data contracts for Home, A/B/C, Settings, and History.
