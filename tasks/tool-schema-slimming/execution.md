# Tool Schema Slimming

## Objective & Hypothesis

- Objective: reduce provider input token overhead from high-churn agent tool schemas without changing tool execution behavior.
- Hypothesis: model catalog discovery should live in `model.metadata` results and runtime validation, not repeated JSON Schema enums. `data.feature.select` should expose only the role binding fields the model must provide; role kind and metadata can remain service-derived or compatibility inputs without being provider-facing schema surface.

## Guardrails Touched

- Typed input: Constraint. Product capability and tool handlers remain the same; provider-facing schema projection becomes leaner.
- Durable owner: `src/xenix/services/agent/tools.py` owns the Agent tool registry schema.
- Blast radius:
  - Provider request tool schemas for `model.metadata` and `data.feature.select`.
  - Agent harness tests that assert tool schema shape.
  - No changes to `data.clean`, ML registry validation, role binding persistence, or training/apply behavior.
- Invariants:
  - `model.metadata` must still accept canonical model keys and supported aliases at execution time.
  - `data.feature.select` must still create the same column binding payloads.
  - Training tools continue validating model keys through runtime catalog logic.
  - Historical bindings that include `role_kind` remain valid at lower service/storage layers.

## Verification

- Updated first-slice schema tests to assert:
  - `model.metadata.model_keys.items` has no enum.
  - `data.feature.select.model_key` has no enum.
  - `data.feature.select.role_bindings.items.properties` is only `role` and `columns`.
- Ran `.\.venv\Scripts\python.exe -m pytest tests\test_agent_harness_first_slice.py -q`.
  - Result: 13 passed.
  - Note: pytest emitted a Windows temp symlink cleanup `PermissionError` after the passing result.
- Ran `.\.venv\Scripts\python.exe -m pytest tests\test_agent_harness_streaming.py -q`.
  - Result: 12 passed.
  - Note: same Windows temp symlink cleanup `PermissionError` after the passing result.
- Re-measured compact provider tool JSON:
  - all 11 tools: 9459 chars -> 7852 chars.
  - `model.metadata`: 1702 chars -> 963 chars.
  - `data.feature.select`: 1414 chars -> 546 chars.
  - `data.clean`: unchanged at 2297 chars.
- Ran `git diff --check`.
  - Result: no whitespace errors.
