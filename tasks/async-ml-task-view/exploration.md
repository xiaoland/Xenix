# Async ML Task View Exploration

## Objective & Hypothesis

- Objective: Convert long-running model training and hyperparameter tuning from blocking Agent tool execution into visible background ML tasks, with a UI surface for task status, logs, cancellation, and results.
- Hypothesis: Returning `task_ids` immediately from long-running model tools, then projecting those tasks through a dedicated ML Task view, will remove avoidable Agent timeouts while making slow local ML work more trustworthy for non-technical business users.

## Prompt

- User observed repeated `model.hyper_train` timeout failures.
- Current `model.hyper_train` waits synchronously for ML tasks to finish with a hardcoded 120 second timeout.
- Initial user preference: "tool does not block until training ends; return `task_ids`; UI/Agent later polls task status" plus an ML Task view.
- Refined user preference:
  - Async-capable behavior should apply to `model.train`, `model.hyper_train`, and `model.apply`.
  - More precisely, each tool should wait for a bounded grace period; if work completes quickly, return the normal task result, otherwise return `task_ids` instead of failing on timeout.
  - No independent global ML Tasks List View.
  - Chatbot Tool Call Item should expose an action that opens the corresponding Tool Call Detail View in a standalone window, regardless of whether the tool completed inline or returned a task receipt.
  - Composer Stop should stop the currently running tool and its active ML tasks.
  - Add `model.task.query` so Agent can inspect ML task metadata, status, and logs for follow-up and failure diagnosis.
  - `model.task.query` should require explicit `task_ids`; no `include_related` option.
  - Do not introduce `task_group_id`; ML tasks remain individual persisted tasks.

## Guardrails Touched

- `docs/20-product-tdd/runtime-boundaries.md`: UI renders ML task status, validation errors, and result locations; services own workflow semantics and persisted task metadata.
- `docs/20-product-tdd/ml-task-lifecycle.md`: MLTask has stable identity, type, status, timestamps, logs, artifacts, and terminal failure semantics.
- `docs/30-unit-tdd/agent-harness.md`: Agent Harness owns tool-call/result records, tool execution sequencing, cancellation, and Chatbot Event projection.
- `docs/30-unit-tdd/chatbot-ui.md`: Chatbot UI consumes projected events and must not infer tool semantics from storage rows.
- `src/xenix/services/AGENTS.md`: Agent Harness owns tool execution; ML service owns ML lifecycle; storage provides persistence.
- `src/xenix/services/ml/AGENTS.md`: Each persisted MLTask is one model and one operation; sequential execution is intentional in v1.

## Current Facts

- `model.hyper_train` creates one tuning task per selected model, then waits for all new dataset tasks to become terminal.
- The blocking wait lives in `src/xenix/services/agent/tools.py` with `timeout_seconds: float = 120.0`.
- The wait also expects follow-up evaluation tasks for supervised models, so one hyperparameter tuning request can produce multiple MLTask rows.
- `MLTaskService` already queues tasks, dispatches them on a background thread, persists statuses, supports cancellation, and stores task logs/artifacts.
- `MLService.get_task_details()` already returns a task, its artifacts, and logs.
- `MLTaskRow` does not currently contain `parent_task_id`, `task_group_id`, `thread_id`, `turn_id`, or `tool_call_id`.
- Follow-up evaluation tasks record their source training task inside request payload as `evaluate_model.source_ml_task_id`, but that is not a first-class grouping field.
- `TaskLogView` exists in the UI, but there is no visible ML Task list/detail surface yet.
- MainWindow currently has a left History sidebar and a central Chatbot thread detail view. There is no right-side operational panel or task drawer.
- Settings `Timeout` is LLM HTTP timeout, not ML tool wait timeout.
- Composer Stop currently cancels the active Agent run. During synchronous ML waits, Agent tool code can observe cancellation through `ToolExecutionContext.cancel_requested` and call `MLService.cancel_task(...)`.
- Once a tool returns a background task receipt and the Agent turn ends, Composer Stop is no longer available for that task; background cancellation needs a task-scoped UI action.
- `ToolCallItem` currently supports expand/collapse detail and artifact links, but no explicit action buttons.

## Unknowns

- Should Agent continue the conversation after task completion automatically, or should completion be surfaced in UI and require the user to ask for analysis?
- Do we need persistent thread-to-MLTask ownership metadata beyond dataset id, turn id, and tool call id?
- Should a background completed task create a new assistant message, a system/control event, or only update the task view?
- Should task-scoped UI actions be inline buttons, an overflow menu, or a hybrid layout?

## Constraints Observed

- UI must not query SQLite directly or infer business semantics outside service projections.
- Agent Harness projection rules should remain authoritative for Chatbot tool events.
- MLTask lifecycle must preserve existing allowed transitions.
- Sequential ML execution is intentional in v1, so the UI should explain queue position and current running task rather than implying parallel execution.
- Non-technical users need task status phrased as business progress, not internal queue mechanics.
- Long-running training must remain cancellable without killing unrelated tasks.

## Candidate Product Shape

1. ML tools become grace-period async tools
   - `model.train`, `model.hyper_train`, and `model.apply` validate inputs and create MLTask rows.
   - Each tool waits only for a bounded grace period.
   - If all required work reaches terminal success during the grace period, return the current rich result shape.
   - If work is still pending/running, return a task receipt with task ids, dataset id, operation, model keys or trained model id, current statuses, and a provider-visible hint to call `model.task.query`.
   - If work fails during the grace period, return the normal tool failure with persisted task id and error summary.

2. Chatbot Tool Call Item becomes the task entry point
   - No global/right-side ML Tasks List View.
   - Every ML tool call item should expose an action to open its corresponding ML Task View, even when the tool completed inline.
   - Tool summary distinguishes completed inline vs still running in background.
   - Detail area includes task ids for traceability and any artifacts/results already available.

3. Tool Call Detail View is task-scoped and standalone
   - Opened from a Tool Call Item action.
   - Shows details for one tool call, not all tasks globally.
   - For ML tools, it shows the ML tasks created by that tool call.
   - For train/hyper train, it can show root training/tuning tasks and any evaluation tasks discoverable from existing payload relationships, but it must not introduce `task_group_id`.
   - For apply, it shows the apply task, output artifact when ready, and logs/errors.
   - Actions include refresh, cancel for pending/running tasks, open artifacts, and view logs.

4. Follow-up Agent affordance
   - Add `model.task.query`.
   - Query by explicit `task_ids`.
   - Return metadata, current status, timestamps, task type, model/dataset fields, result payload summary, artifacts, error summary, and logs.
   - This lets the Agent answer "what happened?", summarize completed results, and diagnose failed tasks without relying on UI-only state.

5. Cancellation behavior
   - During grace-period waiting, Composer Stop cancels the active Agent run and any ML tasks already created by the current tool.
   - After the tool returns a background task receipt, the Agent run is over; cancellation must be available from the Tool Call Item or standalone ML Task View.

## Candidate UI Layout

- Main shell:
  - Left History sidebar and central Chat thread remain unchanged.
  - No persistent right-side task panel.

- Tool Call Item action layout:
  - Primary action: "Details".
  - Direct action: "Cancel" while related tasks are pending/running.
  - Secondary actions should collapse behind an overflow menu if more are added.
  - Keep expand/collapse for result detail.
  - Avoid making task ids the primary UI text; keep them in details.

- Standalone Tool Call Detail View:
  - Header with operation, model, status, started/finished time.
  - Actions: cancel for pending/running, open output for succeeded artifacts, retry later if product decides.
  - Result section: trained model id, primary metric when evaluation exists, artifact links.
  - Logs section: reuse `TaskLogView`.
  - Error section: concise persisted error summary plus log link.

## Candidate Implementation Paths

1. Grace-period async for train/hyper train/apply
   - Shared helper creates tasks, waits briefly, and returns either completed result or background task receipt.
   - Keeps fast operations feeling synchronous while preventing long operations from failing due to local training duration.
   - Requires tool result payloads and Chatbot projection to distinguish `completed` vs `running_background`.

2. Task-scoped Tool Call Detail View window
   - Add a UI dialog/window opened from Tool Call Item action metadata.
   - It queries service-level task projections by task ids.
   - Avoids persistent task navigation and keeps task context anchored to the originating chat action.

3. Add `model.task.query`
   - Expose task metadata/status/logs to the Agent.
   - Can later support richer filters, but first slice should require explicit task ids to avoid ambiguous global state.

## Verification Anchors

- Agent Harness tests prove async model tool result persists tool-call/result messages without waiting for terminal MLTask status.
- Agent Harness tests prove completed-within-grace tools still return the current rich result shape.
- ML service tests prove created tasks still execute and produce follow-up evaluation tasks.
- UI tests prove Tool Call Item exposes task actions when task ids exist.
- UI tests prove standalone Tool Call Detail View displays pending/running/succeeded/failed/cancelled tasks, logs, artifacts, and cancel action.
- Boundary tests prove UI consumes service-provided task projections, not raw SQLite.
- Agent tool tests prove `model.task.query` returns task metadata, status, logs, artifacts, and error summaries.
- Manual smoke: start hyperparameter tuning with a deliberately large grid; the Chatbot turn returns quickly, task view shows running state, and completion later exposes artifacts/logs.

## Smallest Confirmation Needed

- Confirm Tool Call Item action layout.
- Confirm whether the first slice needs a service-level Tool Call Detail projection object, or whether the UI can compose from existing Agent tool result payload plus ML service task details.

## Product Decisions

- Use `Tool Call Detail View`, not `ML Task View`, because the entry point is a Chatbot tool call and the surface can later generalize beyond ML-only details.
- Keep direct Cancel on the Tool Call Item for running background ML tasks.
- Composer Stop only cancels the currently active Agent/tool execution before the tool returns.
- `model.task.query` requires explicit `task_ids` and does not include `include_related`.
- Never introduce `task_group_id`; use explicit task ids and existing payload references only.
- Grace-period defaults:
  - `model.apply`: 30 seconds.
  - `model.train`: 60 seconds.
  - `model.hyper_train`: 60 seconds.

## Promotion Candidate Truths

- Pending user confirmation.
