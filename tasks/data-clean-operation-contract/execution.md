# Data Clean Operation Contract

## Objective & Hypothesis

- Objective: replace the policy-bundle `data.clean` schema with an operation-centric executor and add `data.clean.metadata` for operation parameter schema discovery.
- Hypothesis: keeping `data.clean` as a thin `{operation, params}` executor and moving detailed operation schemas behind metadata reduces always-attached provider schema cost while preserving deterministic Pandas-backed cleaning behavior.

## Guardrails Touched

- Typed input: Constraint. Product capability stays within predefined atomic cleaning operations; the LLM-facing contract changes.
- Durable owners:
  - `src/xenix/services/data_cleaning.py` owns deterministic operation execution.
  - `src/xenix/services/agent/tools.py` owns provider-facing tool schemas and metadata discovery.
- Blast radius:
  - `data.clean` provider schema and runtime argument shape.
  - Agent static registry and contextual `data.*` exposure.
  - Data-cleaning tests and Agent Harness tests.
  - Runtime-boundary and Agent Harness docs.
- Invariants:
  - Source datasets remain unchanged.
  - Non-empty cleaning operations still create derived dataset artifacts.
  - Empty or absent operations perform no cleaning and register no derived artifact.
  - `data.clean.metadata` never executes cleaning.
  - No legacy compatibility is retained for `drop_duplicates`, `duplicate_policy`, `missing_policy`, `type_corrections`, `text_standardization`, or `validation_rules`.

## Verification

- Updated data-cleaning tests to cover:
  - Empty operation list as no-op.
  - Operation-centric execution for type conversion, text operations, missing fill, validation drop rows, and duplicate key removal.
  - `data.clean` no-op tool result with no derived artifact registration.
  - Runtime rejection of legacy policy fields.
  - `data.clean.metadata` group schema lookup.
  - Thin `data.clean` and `data.clean.metadata` schema shape.
- Updated Agent Harness tests to include `data.clean.metadata` in contextual `data.*` exposure.
- Ran `.\.venv\Scripts\python.exe -m pytest tests\test_data_cleaning.py -q`.
  - Result: 7 passed.
  - Note: pytest emitted a Windows temp symlink cleanup `PermissionError` after the passing result.
- Ran `.\.venv\Scripts\python.exe -m pytest tests\test_agent_harness_first_slice.py -q`.
  - Result: 13 passed.
  - Note: same Windows temp symlink cleanup `PermissionError` after the passing result.
- Ran `.\.venv\Scripts\python.exe -m pytest tests\test_agent_harness_streaming.py -q`.
  - Result: 12 passed.
  - Note: same Windows temp symlink cleanup `PermissionError` after the passing result.
- Ran `.\.venv\Scripts\python.exe -m pytest tests\test_data_transform.py -q`.
  - Result: 7 passed.
  - Note: same Windows temp symlink cleanup `PermissionError` after the passing result.
- Ran `.\.venv\Scripts\python.exe -m compileall src tests scripts`.
  - Result: passed.
- Re-measured compact provider tool JSON:
  - all 12 tools: 6406 chars.
  - `data.clean`: 571 chars.
  - `data.clean.metadata`: 280 chars.
