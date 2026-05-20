# Inline Inference Input Execution

## Objective & Hypothesis

- Objective: Allow `model.inference` to accept inline tabular rows in addition to existing input files.
- Hypothesis: The smallest correct change is to add an `input_rows` table payload at the Agent tool and ML service boundary, materialize it to the existing manual-inference CSV path, and keep worker execution unchanged.

## Pre-Execution Restatement

- Target: Agent Harness `model.inference` and `MLService.infer`.
- Current state and context: `model.inference` requires `input_files`; `MLService.infer` validates file inputs against trained model feature metadata before creating an inference task.
- Operation: Add `input_rows` shaped as `{header_index_map, data}`. Require at least one of `input_files` or `input_rows`.
- Scope included: Tool schema, tool handler, ML service input normalization/materialization, tests, and unit boundary docs.
- Scope excluded: UI manual-entry widgets, ML worker request format changes, generic script execution, persisted schema changes.
- Invariants: Existing file-based inference remains compatible. ML worker still receives `InferenceTaskRequest.input_files`. Trained model metadata remains the feature-column contract.
- Likely affected files: `src/xenix/services/agent/tools.py`, `src/xenix/services/ml_service.py`, `tests/test_agent_harness_first_slice.py`, `tests/test_ml_execution.py`, `docs/30-unit-tdd/agent-harness.md`, `docs/20-product-tdd/runtime-boundaries.md`.
- Uncertainty: Whether mixed file and inline inputs should be accepted in one call. Accepted for now because the existing worker already supports multiple input files.

## Guardrails Touched

- Agent Harness owns tool schema and execution.
- ML service owns inference workflow inputs and feature contract validation.
- Dataset service owns manual inference CSV materialization.

## Plan

1. Extend typed inference input models and service normalization.
2. Extend `model.inference` tool schema and handler.
3. Add focused tests for inline-only and schema behavior.
4. Update durable contract docs and run targeted tests.

## Verification

- Command: `pdm run pytest tests/test_ml_execution.py tests/test_agent_harness_first_slice.py -q`
- Expected: Targeted Agent Harness and ML execution tests pass.
- Observed: `11 passed in 56.75s`. Pytest emitted a Windows temp symlink cleanup `PermissionError` after completion, but the command exited successfully.
- Command: `pdm run python -m compileall src tests`
- Expected: Source and tests compile successfully.
- Observed: Passed.

## Promotion Notes

- Durable truth candidates: `model.inference` accepts file inputs or inline table inputs.
- Keep in task only: Implementation details of temporary CSV materialization.
