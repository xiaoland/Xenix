# Message-Centric Chat Streaming

## Objective & Hypothesis

- Objective: Make running Chatbot turns render persisted timeline messages, including tool-call and tool-result messages, before the turn ends.
- Hypothesis: The durable model already treats tool-call and tool-result as message kinds; the missing foundation is a message-centric streaming contract between Agent Harness and Chatbot UI.

## Pre-Execution Restatement

- Target: `src/xenix/services/agent/`, `src/xenix/services/storage/`, `src/xenix/ui/`, affected tests, and governing unit TDD docs.
- Current state and context: Agent Harness persists tool-call/tool-result messages during an open turn but only sends a final full snapshot; the UI receives provider deltas and final snapshots rather than canonical message events.
- Operation: Add message lifecycle fields, emit message-level stream events after persisted message create/update/finalize operations, and make Chatbot UI render those events as timeline updates.
- Scope included: message lifecycle schema, stream event shape, harness stream emission, incremental UI rendering, tests, docs.
- Scope excluded: provider API changes, tool execution semantics, artifact service behavior, visual redesign.
- Invariants: Chatbot timeline renders from canonical messages; Agent Harness owns message/tool execution semantics; full snapshots remain the authority for thread initialization and final convergence.
- Likely affected files: `storage/models.py`, `storage/migrations.py`, `agent/conversation_store.py`, `agent/harness_service.py`, `ui/chatbot.py`, `ui/main_window.py`, `tests/test_agent_harness_streaming.py`, `tests/test_main.py`, storage tests, unit TDD docs.
- Uncertainty: Whether assistant streaming should persist partial text for every delta immediately or remain in-memory until finalization while still exposing only message events to UI.

## Guardrails Touched

- Chatbot UI must stay service-driven and render from Agent Harness-owned messages.
- Agent Harness owns Thread, Turn, Message, tool-call, tool-result, run recording, provider interaction, and tool execution.
- Non-trivial work requires task packet, explicit verification, and durable docs update.

## Plan

1. Extend message model with lifecycle status and timestamps.
2. Introduce message-centric stream event fields and helpers.
3. Emit message events for assistant streaming lifecycle, tool-call creation, and tool-result creation.
4. Apply message events incrementally in Chatbot UI.
5. Cover storage, harness stream, and UI event behavior with tests.
6. Update unit TDD docs with the new contract.

## Verification

- Command: `python -m compileall src tests`
- Expected: Source and test modules compile after contract and schema changes.
- Observed: Passed.

- Command: `pdm run pytest tests/test_agent_harness_streaming.py tests/test_main.py tests/test_storage_bootstrap.py tests/test_migrations.py`
- Expected: Harness streaming, Chatbot UI, storage bootstrap, and migration boundaries pass.
- Observed: 36 passed. Pytest emitted a Windows temp-directory cleanup `PermissionError` after reporting success.

- Command: `pdm run pytest`
- Expected: Full repository test suite passes after schema and streaming contract changes.
- Observed: 84 passed. Pytest emitted the same Windows temp-directory cleanup `PermissionError` after reporting success.

- Command: `pdm run pytest tests/test_storage_bootstrap.py tests/test_agent_harness_streaming.py tests/test_main.py tests/test_migrations.py`
- Expected: Message status migration rows using lowercase values and any rows briefly written with uppercase enum names are ORM-readable.
- Observed: 36 passed. Pytest emitted the same Windows temp-directory cleanup `PermissionError` after reporting success.

- Command: `pdm run pytest`
- Expected: Full suite remains green after message status enum storage fix.
- Observed: 84 passed. Pytest emitted the same Windows temp-directory cleanup `PermissionError` after reporting success.

- Command: `pdm run smoke`
- Expected: Application bootstrap succeeds after reading migrated message status rows.
- Observed: Passed; smoke test completed.

- Command: `pdm run pytest tests/test_storage_bootstrap.py tests/test_migrations.py tests/test_agent_harness_streaming.py tests/test_main.py`
- Expected: v3 databases containing uppercase `AgentMessageStatus` names are migrated forward to lowercase values; ORM remains strict value-based after migration.
- Observed: 37 passed. Pytest emitted the same Windows temp-directory cleanup `PermissionError` after reporting success.

- Command: `pdm run pytest`
- Expected: Full suite remains green after replacing status read tolerance with v3-to-v4 data migration.
- Observed: 85 passed. Pytest emitted the same Windows temp-directory cleanup `PermissionError` after reporting success.

- Command: `pdm run smoke`
- Expected: Application bootstrap succeeds after v4 migration path.
- Observed: Passed; smoke test completed.

- Command: `rg -n 'user_version=2|schema version `2`|baseline.*2|SQLite `user_version=2`|CURRENT_SCHEMA_VERSION == 3|schema version `3`|user_version=3' docs AGENTS.md src\xenix\services\AGENTS.md -S`
- Expected: Durable docs no longer advertise obsolete schema baselines.
- Observed: No matches.

## Promotion Notes

- Durable truth candidates: Promoted into `docs/30-unit-tdd/agent-harness.md` and `docs/30-unit-tdd/chatbot-ui.md`.
- Keep in task only: implementation notes and local verification output.
