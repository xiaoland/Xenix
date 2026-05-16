# Phase 1 First-Slice Execution

## Objective & Hypothesis

Implement the first executable ChatBox-first slice behind the Native AI First design:

- Persist Agent Harness threads, turns, messages, tool calls, run records, and artifact records.
- Refactor ML service inputs so the Agent Harness can train, evaluate, and infer from explicit dataset/feature/target/model inputs.
- Provide a static tool registry for the first-slice tools: `turn_end`, `data.peek`, `data.integrate`, `data.clean`, `data.feature.select`, `model.train`, `model.hyper_train`, and `model.inference`.
- Replace the default Qt center surface with a ChatBox shell and route submitted messages into Agent Harness.

The hypothesis is that a first-slice user journey can be proven without WorkItem as the primary workspace by deriving working context from messages, tool results, and artifacts.

## Guardrails Touched

- `src/xenix/services/storage/`: schema v7, Agent Harness records, generic artifact records, dataset-scoped task/model queries.
- `src/xenix/services/ml_service.py`: dataset-scoped training, tuning, inference inputs added while preserving WorkItem-compatible entrypoints.
- `src/xenix/services/ml_task_service.py`: `work_item_id` is optional for ML task execution and canonical output paths can be dataset-scoped.
- `src/xenix/services/agent/`: provider boundary, Harness loop, static tool registry, tool execution context.
- `src/xenix/services/agent/`: step budget is now a user-confirmed pause/resume contract when the current budget is exhausted.
- `src/xenix/services/agent/`: active runs now carry a cooperative cancellation signal used by provider loops and tool execution context.
- `src/xenix/ui/`: ChatBox is now the default main surface; legacy widgets remain instanced for compatibility while target flow moves to ChatBox.
- `src/xenix/ui/`: ChatBox owns the step-budget confirmation control surfaced from Agent Harness stream events.
- `src/xenix/ui/`: ChatBox renders provider-wait `Thinking...` and non-`turn_end` tool-call messages in the message list.

## Verification

- `python -m compileall src tests`
- `pdm run pytest tests/test_agent_harness_foundation.py tests/test_storage_bootstrap.py tests/test_migrations.py tests/test_repositories.py`
- `pdm run pytest tests/test_ml_execution.py`
- `pdm run pytest tests/test_services.py tests/test_inference_history.py`
- `pdm run pytest tests/test_main.py tests/test_agent_harness_foundation.py tests/test_agent_harness_first_slice.py`
- `pdm run pytest`

Full-suite result: `78 passed in 203.48s`.

## Current Gaps

- Step budget exhaustion pauses the Agent run and waits for user confirmation before continuing.
- The ChatBox stop button now immediately requests Agent Harness cancellation and returns the UI to an editable state; tool wait loops and spawned ML worker processes observe cancellation cooperatively.
- OpenAI-compatible provider is present, with canonical tool names mapped to provider-safe function names. CopilotKit AIMock HTTP boundary remains a follow-up adapter/test harness task.
- Artifact preview rendering is link-based in ChatBox. Rich inline table/image preview remains a UI follow-up.
