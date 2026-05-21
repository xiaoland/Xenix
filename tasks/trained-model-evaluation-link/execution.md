# Trained Model Evaluation Link Execution

## Objective & Hypothesis

- Objective: Stop using dataset task-list diffs to link `model.train` / `model.hyper_train` root tasks with follow-up evaluation work.
- Hypothesis: The trained model is the correct aggregate boundary. Training returns a `trained_model_id`; follow-up evaluation should attach its task id and metrics to trained-model metadata; Agent tools should wait and summarize through that model relation.

## Guardrails Touched

- `docs/20-product-tdd/ml-task-lifecycle.md`
- `docs/20-product-tdd/runtime-boundaries.md`
- `docs/30-unit-tdd/agent-harness.md`
- `src/xenix/services/AGENTS.md`

## Plan

1. Add trained-model metadata support for the evaluation ML task id.
2. Attach the evaluation task id to the trained model when follow-up evaluation is submitted, and keep metrics attached when evaluation completes.
3. Change Agent train/hyper-train waiting and receipt aggregation to use root task ids -> trained model ids -> evaluation task ids.
4. Remove `evaluate_model.source_ml_task_id` from the forward request contract so `trained_model_id` is the relation source.
5. Update focused tests and run verification.

## Verification

- Command: `pdm run check`
  Expected: changed source and tests compile.
  Observed: passed after removing `evaluate_model.source_ml_task_id`.
- Command: `pdm run pytest tests\test_ml_execution.py tests\test_agent_harness_first_slice.py tests\test_agent_harness_foundation.py`
  Expected: ML execution and Agent tool paths still pass after switching training aggregation to trained-model relations.
  Observed: 21 passed. Pytest emitted the existing Windows temp symlink cleanup `PermissionError` after completion.
- Command: `pdm run test`
  Expected: full suite passes.
  Observed: 117 passed in 120.61s after removing `evaluate_model.source_ml_task_id`. Pytest emitted the same Windows temp symlink cleanup `PermissionError` after completion.
