# ChatBox History Sidebar

## Objective & Hypothesis

Add a left-side conversation history surface and seed local SQLite with mock Agent Harness turns/messages so message rendering can be inspected quickly during UI iteration.

## Guardrails Touched

- `ConversationStore` now exposes `list_threads()`.
- `AgentHarnessService` exposes thread listing and snapshot loading for UI.
- Thread mock data is test-owned through `services/agent/dev_fixtures.py`; runtime bootstrap does not seed mock conversations into SQLite.
- `MainWindow` renders a left-side history sidebar and loads selected thread snapshots into ChatBox.

## Verification

- `python -m compileall src tests`
- `pdm run pytest tests/test_main.py tests/test_agent_harness_foundation.py tests/test_agent_harness_first_slice.py`
- `pdm run pytest`

Full-suite result: `80 passed in 186.65s`.

Update: runtime mock seeding was removed during the storage schema reset cleanup. Tests that need the rendering fixture call `ensure_mock_conversation_history()` explicitly.
