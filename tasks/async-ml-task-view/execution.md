# Async Tool Call Detail Execution

## Objective & Hypothesis

- Objective: Implement grace-period async behavior for `model.train`, `model.hyper_train`, and `model.apply`; expose task details/cancellation from Chatbot Tool Call Items; add `model.task.query` for Agent-visible ML task diagnosis.
- Hypothesis: Returning completed results for fast tasks and task receipts for long tasks will remove ML timeout failures while keeping short workflows ergonomic.

## Pre-Execution Restatement

- Target: Agent ML tools, Chatbot tool-call projection/rendering, and task detail UI.
- Current state and context: ML tools block up to 120 seconds and fail on timeout; Tool Call Items only expand/collapse details; ML tasks already persist status/logs/artifacts and support cancellation.
- Operation: Replace fixed blocking waits with grace-period waits; add task receipt payloads; add explicit task query tool; add Tool Call Item Details/Cancel actions and standalone Tool Call Detail View.
- Scope included: `model.train`, `model.hyper_train`, `model.apply`, `model.task.query`, task action metadata/projection, UI action wiring, task detail/cancel service use.
- Scope excluded: global ML task list, `task_group_id`, implicit related-task querying in Agent tool schema, storage migrations.
- Invariants: UI must not query SQLite directly; Agent Harness remains owner of tool-call records/projection; MLTask lifecycle states remain unchanged; Composer Stop cancels only active run/tool.
- Likely affected files: `src/xenix/services/agent/tools.py`, `src/xenix/services/agent/chatbot_events.py`, `src/xenix/ui/chatbot.py`, `src/xenix/ui/main_window.py`, `src/xenix/app.py`, tests.
- Uncertainty: Exact UI test coverage available for Qt action buttons may be limited; implementation may require focused service/tool tests plus manual smoke.

## Guardrails Touched

- `docs/20-product-tdd/runtime-boundaries.md`
- `docs/20-product-tdd/ml-task-lifecycle.md`
- `docs/30-unit-tdd/agent-harness.md`
- `docs/30-unit-tdd/chatbot-ui.md`
- `src/xenix/services/AGENTS.md`
- `src/xenix/services/ml/AGENTS.md`
- `src/xenix/ui/AGENTS.md`

## Plan

1. Add Agent tool grace-period helpers and `model.task.query`.
2. Add task action metadata to Chatbot Event projection and render Details/Cancel buttons in Tool Call Item.
3. Add standalone Tool Call Detail View and wire MainWindow to query/cancel task details through services.
4. Add focused tests for async receipt/query/projection and run target tests.

## ML Task Enum Storage Fix Addendum

- Objective: Fix existing local SQLite rows that can make `model.train` or `model.hyper_train` fail while listing dataset ML tasks because historical ML task enum names such as `INFERENCE` are not valid in the current strict ORM mapping.
- Hypothesis: Persisting ML task type, status, and artifact-kind enum values explicitly, then migrating old enum names and obsolete inspect-dataset task rows in a v10 data migration, keeps fresh and upgraded databases readable without tolerant ORM shims.
- Guardrails Touched: `docs/40-deployment/local-state-evolution.md`, `docs/40-deployment/runtime-state.md`, `docs/20-product-tdd/storage-ownership.md`, `src/xenix/services/AGENTS.md`.
- Verification: `pdm run check` passed; `pdm run pytest tests\test_migrations.py tests\test_repositories.py tests\test_ml_execution.py tests\test_agent_harness_first_slice.py tests\test_storage_bootstrap.py` passed with 35 tests; `pdm run test` passed with 117 tests. Pytest emitted the existing Windows temp symlink cleanup `PermissionError` after completion.

## Verification

- Command: `python -m compileall src\xenix`
  Expected: source compiles.
  Observed: passed.
- Command: `pdm run pytest tests/test_agent_harness_first_slice.py tests/test_agent_harness_foundation.py tests/test_main.py tests/test_i18n.py`
  Expected: focused Agent/UI/i18n tests pass.
  Observed: 44 passed. Pytest emitted a Windows temp symlink cleanup `PermissionError` after completion, but test result was successful.
- Command: `pdm run check`
  Expected: compileall check passes for src/tests/scripts.
  Observed: passed.
- Command: `pdm run test`
  Expected: full suite passes.
  Observed: 116 passed in 111.58s after the final input-validation adjustment. Pytest emitted the same Windows temp symlink cleanup `PermissionError` after completion.
- Command: `pdm run pytest tests/test_ml_execution.py tests/test_services.py tests/test_repositories.py tests/test_storage_bootstrap.py tests/test_migrations.py tests/test_agent_harness_first_slice.py`
  Expected: storage/ML/Agent paths still pass after removing `inspect_dataset` from `MLTaskType`.
  Observed: 40 passed. Pytest emitted the same Windows temp symlink cleanup `PermissionError` after completion.
- Command: `pdm run test`
  Expected: full suite still passes after removing `inspect_dataset` from `MLTaskType`.
  Observed: 116 passed in 123.16s. Pytest emitted the same Windows temp symlink cleanup `PermissionError` after completion.
- Command: `pdm run check`
  Expected: source, tests, and scripts compile after the ML task enum storage migration.
  Observed: passed.
- Command: `pdm run pytest tests\test_migrations.py tests\test_repositories.py tests\test_ml_execution.py tests\test_agent_harness_first_slice.py tests\test_storage_bootstrap.py`
  Expected: storage, repository, ML execution, and Agent tool paths still pass after migrating ML task enum persistence to lowercase values.
  Observed: 35 passed. Pytest emitted the same Windows temp symlink cleanup `PermissionError` after completion.
- Command: `pdm run test`
  Expected: full suite passes after the v10 migration and enum storage mapping changes.
  Observed: 117 passed in 128.13s. Pytest emitted the same Windows temp symlink cleanup `PermissionError` after completion.
- Command: `pdm run smoke`
  Expected: app smoke path starts and exits successfully.
  Observed: passed.
- Command: `pdm run i18n-extract`; `pdm run i18n-compile`
  Expected: translations updated/compiled; zh_CN has no unfinished entries.
  Observed: passed; zh_CN reports 155 finished and 0 unfinished.

## Promotion Notes

- Durable truth candidates: promoted to runtime, Agent Harness, Chatbot UI, and ML task lifecycle docs.
- Keep in task only: implementation notes and pytest temp cleanup observation.
