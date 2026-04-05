# Issue 80 - Existing Plan Review v1

## Review Scope

This review checks whether the current planning stack under `tasks/issue-80/` is:

1. internally consistent,
2. aligned with GitHub issue `#80`,
3. compatible with the current codebase and local service constraints.

This is a design review only. No production code changes are proposed here.

## Inputs Reviewed

- GitHub issue `#80`: `https://github.com/xiaoland/Xenix/issues/80`
- `tasks/issue-80/L0-PLAN.md`
- `tasks/issue-80/L1-PLAN.md`
- `tasks/issue-80/L2-PLAN.md`
- `tasks/issue-80/L2-UX-ADAPTATION-PLAN.md`
- `tasks/issue-80/ISSUE-80-DESCRIPTION-v1.md`
- current UI/service code:
  - `src/xenix/ui/main_window.py`
  - `src/xenix/ui/dataset_workspace.py`
  - `src/xenix/ui/ml_workspace.py`
  - `src/xenix/ui/inference_workspace.py`
  - `src/xenix/services/work_item_service.py`
  - `src/xenix/services/ml_service.py`
  - `src/xenix/services/ml_task_service.py`
  - `src/xenix/services/ml/contracts.py`

## What Is Already Solid

### 1. L0 did its job

`L0-PLAN.md` correctly converted a vague product request into a bounded problem statement:

- scenario-first UX
- guided `A -> B -> C` flow
- standalone settings
- inference-result-centric history

It also captured the correct current-vs-target gap.

### 2. L1 is effectively the current issue definition

The current GitHub issue body is already almost the same as `ISSUE-80-DESCRIPTION-v1.md`, which itself is derived from `L1-PLAN.md`.

That means:

- issue scope is no longer the main uncertainty,
- implementation feasibility is now the main uncertainty.

### 3. The reuse direction is sensible at a high level

The codebase does already have reusable raw materials:

- dataset import and column-selection widgets in `DatasetWorkspace`
- task tables, logs, and trained-model lists in `MLWorkspace`
- manual/batch inference surfaces and result actions in `InferenceWorkspace`

So the general reuse-first instinct is reasonable.

## Findings

### Finding 1. L2 workflow metadata is underspecified and cannot work as written

Severity: high

`L2-PLAN.md` proposes attaching `workflow_context` into task request payloads without schema migration. The "no schema migration" part is fine, but the current request models do not contain such a field:

- `src/xenix/services/ml/contracts.py`
- `src/xenix/services/ml_service.py`

Current task payload persistence happens through `request.model_dump(mode="json")` in `MLService._create_task_from_request`. Only declared model fields are serialized. Under the current contracts, any scenario/session metadata would be dropped unless the request model classes are extended first.

Practical consequence:

- history traceability by scenario template will not exist,
- branch/run/session grouping will not exist,
- L2 history design depends on data that the current contracts do not preserve.

Required correction:

- explicitly add `workflow_context` to the relevant request contracts,
- thread it through fit, tuning, evaluate, and inference creation paths,
- state that this is a request-contract change, not just a free JSON add-on.

### Finding 2. The hidden-project strategy is still unresolved, but the whole UX depends on it

Severity: high

Current code is project-centric end to end:

- `DatasetWorkspace` requires project selection before dataset registration and work-item creation.
- `WorkItemService.create_work_item(...)` requires `project_id`.
- `MLWorkspace` and `InferenceWorkspace` both load work items through the selected project.

References:

- `src/xenix/ui/dataset_workspace.py`
- `src/xenix/services/work_item_service.py`
- `src/xenix/ui/ml_workspace.py`
- `src/xenix/ui/inference_workspace.py`

`L2-PLAN.md` acknowledges this only indirectly in the approval checklist as "hidden default project strategy". That is too late. It is not a cosmetic detail. It changes:

- Home behavior,
- Window A creation flow,
- session identity,
- backward navigation,
- how existing projects remain accessible.

Required correction:

- decide the product truth before implementation planning:
  - Option A: keep one visible project selector somewhere in scenario mode
  - Option B: auto-create/use a hidden default project
  - Option C: treat scenario sessions as the new top-level container and adapt project usage behind the scenes

Without that decision, L2 is not stable enough.

### Finding 3. ML task parallelism is not a small implementation detail; it is a separate architecture change

Severity: high

The current system is intentionally sequential:

- `MLTaskService` owns one queue and one dispatcher thread in `src/xenix/services/ml_task_service.py`
- local ML guidance states: "Sequential execution is intentional in v1: only one worker process runs at a time." in `src/xenix/services/ml/AGENTS.md`

`L2-PLAN.md` replaces that with bounded parallel dispatch. That may still be the right product decision, but it is not a routine follow-up to a UI redesign. It affects:

- scheduler behavior,
- failure handling,
- continuation timing,
- best-model update ordering,
- test strategy,
- packaged runtime stability on low-spec devices.

Required correction:

- either split parallel execution into an explicit child design/work item,
- or keep it in issue `#80` but acknowledge that issue `#80` is not only a UX refactor.

Current L2 underestimates this scope expansion.

### Finding 4. Reuse is plausible for Window A, but optimistic for Windows B/C unless extraction seams are named more concretely

Severity: medium

`DatasetWorkspace` already composes visible reusable widgets:

- `FileDropZone`
- `DatasetSummaryWidget`
- `ColumnSelectionWidget`

So Window A can probably be adapted with moderate extraction.

By contrast, `MLWorkspace` and `InferenceWorkspace` are more monolithic. They combine:

- context selectors,
- submit actions,
- polling/refresh loops,
- task/detail rendering,
- service calls,
- view-specific messaging

References:

- `src/xenix/ui/ml_workspace.py`
- `src/xenix/ui/inference_workspace.py`

That means "reuse-heavy" for B/C may be misleading. The real choice is probably:

- extract a few low-level widgets only, then build new dialogs around them, or
- do larger replacements while preserving service calls.

Required correction:

- replace "reuse-heavy" language with explicit extraction seams,
- list what is truly reusable at widget level versus what should be rebuilt at dialog/panel level.

### Finding 5. L2 mixes stable product truths with speculative implementation shapes

Severity: medium

Examples of stable truths:

- Home is scenario-first
- history is inference-task-centric
- B auto-runs a fixed plan
- C defaults to best model

Examples of speculative implementation choices:

- `ScenarioSession(SQLModel)`
- exact dispatcher-pool shape
- exact service names such as `InferenceHistoryService`
- exact default `max_parallel_tasks = 2`

Those may be good candidate implementations, but they are not all equally mature. Keeping them in one L2 document makes the plan look more settled than it really is.

Required correction:

- separate confirmed product contracts from candidate implementation shapes,
- mark which low-level elements are decisions vs proposals.

## Net Assessment

The planning stack is useful and mostly coherent, but it is not yet execution-safe.

Current maturity by layer:

- `L0`: good
- `L1`: good and already reflected in the GitHub issue
- `L2`: promising but overcommitted in three critical areas:
  - scenario metadata persistence
  - hidden project strategy
  - scheduler parallelism scope

## Smallest Confirmations Needed Before Moving Forward

1. Decide whether project remains a visible user concept in scenario mode.
2. Decide whether parallel ML execution is truly in issue `#80`, or is staged after the UX shell lands.
3. Confirm whether scenario/session metadata must be queryable in history for v1.

If those three are resolved, L2 can be tightened into an execution-grade plan.

## Recommended Next Step

Do not start implementation from the current L2 as-is.

Instead:

1. revise `L2-PLAN.md` to separate confirmed truths from open implementation decisions,
2. add one focused subsection for project-container strategy,
3. add one focused subsection for task-request metadata contract changes,
4. decide whether parallelism stays inside issue `#80` or becomes a staged follow-up.
