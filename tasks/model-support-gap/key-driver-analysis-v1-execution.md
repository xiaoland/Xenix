# Key Driver Analysis V1 Execution Task

## Objective & Hypothesis

- Objective: implement the `Key Driver Analysis V1` slice defined in `key-driver-analysis-v1-solidify.md`.
- Hypothesis: a supervised analysis scenario plus key-driver CSV artifacts can make the planned scenario usable without changing storage or adding dependencies.

## Scope Executed

- Enabled `key_driver_analysis` in `AnalysisScenarioService`.
- Added `key_driver_analysis.v1` scenario template:
  - supervised target required
  - regression-oriented V1 for numeric business targets
  - default steps: `regression.gradient_boosting`, `regression.lasso`
  - post-training behavior ends at result review rather than prediction inference
- Added `ScenarioTemplate.continues_to_prediction` to distinguish prediction workflows from analysis-output workflows.
- Updated scenario routing:
  - prediction/classification keep model-source selection and inference continuation
  - clustering/key-driver analysis route directly to training selection
- Added supervised key-driver report generation in `NumericAndCategoricalModelService`:
  - tree importances via `feature_importances_`
  - linear importances via absolute coefficients
  - source-column aggregation for one-hot encoded categorical features
  - `key_drivers.csv` export artifact
  - compact `top_key_drivers` result summary
- Updated training dashboard:
  - key-driver copy and terminal summary
  - `Close Results` action for key-driver runs
  - top-driver card summary
  - root-task export lookup when a supervised follow-up evaluation exists
- Updated localized template text and translations.
- Added tests for key-driver scenario availability, routing, report artifacts, and output opening.

## Guardrails Touched

- Legacy `F:\CODING\Project\Xenix\ml` scripts stayed read-only.
- Storage schema stayed unchanged.
- `ProblemKind` and `MLTaskType` stayed unchanged.
- Existing prediction/classification inference flow stayed covered by tests.
- Existing clustering route stayed covered by tests.
- Key-driver report generation is best-effort for models with compatible importance attributes.

## Verification

- Command:
  - `pdm run pytest tests/test_ml_execution.py tests/test_scenario_ui.py tests/test_scenario_workflow.py -q`
  - `pdm run i18n-extract`
  - `pdm run i18n-compile`
  - `pdm run pytest tests/test_ml_execution.py tests/test_scenario_ui.py tests/test_scenario_workflow.py tests/test_i18n.py -q`
  - `pdm run python -m compileall src tests scripts`
  - `pdm run pytest -q`
- Observed:
  - targeted ML/UI/workflow suite passed: `36 passed`
  - i18n-aware targeted suite passed: `38 passed`
  - compile succeeded
  - full pytest suite passed: `67 passed`
  - `zh_CN` translation compile reported `456 finished and 0 unfinished`

## Notes

- `key_drivers.csv` contains `rank`, `feature`, `importance`, `raw_importance`, `effect_direction`, and `transformed_feature_count`.
- For supervised tasks with follow-up evaluation, training dashboard now falls back to the root task artifacts when the selected evaluation task has no openable export.
