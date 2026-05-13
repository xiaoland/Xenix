# ChatBox History Sidebar

## Objective & Hypothesis

Add a left-side conversation history surface and seed local SQLite with mock Agent Harness turns/messages so message rendering can be inspected quickly during UI iteration.

## Guardrails Touched

- `ConversationStore` now exposes `list_threads()`.
- `AgentHarnessService` exposes thread listing and snapshot loading for UI.
- `build_main_window()` seeds idempotent dev mock conversations into the current local SQLite database.
- `MainWindow` renders a left-side history sidebar and loads selected thread snapshots into ChatBox.

## Verification

- `python -m compileall src tests`
- `pdm run pytest tests/test_main.py tests/test_agent_harness_foundation.py tests/test_agent_harness_first_slice.py`
- `pdm run pytest`

Full-suite result: `80 passed in 186.65s`.

