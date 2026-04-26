# Anomaly Detection V1 Execution Task

## Objective & Hypothesis

- Objective: implement the `Anomaly Detection V1` slice defined in `anomaly-detection-v1-solidify.md`.
- Hypothesis: native unsupervised anomaly services plus a feature-only scenario template can make anomaly detection usable without new dependencies or storage migrations.

## Scope Executed

- Added `ProblemKind.ANOMALY_DETECTION`.
- Added anomaly default evaluation policy metadata with no split/evaluate.
- Added native anomaly model services:
  - `anomaly.isolation_forest`
  - `anomaly.local_outlier_factor`
- Added `UnsupervisedAnomalyModelService`:
  - feature-only fit path
  - shared numeric/categorical preprocessing
  - anomaly label normalization
  - anomaly score/rank output
  - `anomaly_scores.csv` export artifact
  - anomaly count/rate result summary
- Enabled `anomaly_detection` in `AnalysisScenarioService`.
- Added `anomaly_detection.v1` scenario template:
  - no target column
  - default steps: Isolation Forest and Local Outlier Factor
  - no inference continuation
- Updated training dashboard:
  - anomaly-specific running/finished copy
  - anomaly count/rate card summary
  - output CSV action for anomaly score artifacts
- Updated localized template text and translations.
- Added tests for registry, policy, fit artifact output, scenario routing, dashboard output opening, and workflow completion.

## Guardrails Touched

- Legacy `F:\CODING\Project\Xenix\ml` scripts stayed read-only.
- `MLTaskType` stayed unchanged.
- SQLite table structure stayed unchanged.
- Anomaly V1 stays feature-only with no evaluation or inference gate.
- Existing prediction, classification, clustering, and key-driver routes remain covered by tests.

## Verification

- Command:
  - `pdm run pytest tests/test_ml_registry.py tests/test_ml_execution.py tests/test_scenario_ui.py tests/test_scenario_workflow.py -q`
  - `pdm run i18n-extract`
  - `pdm run i18n-compile`
  - `pdm run pytest tests/test_ml_registry.py tests/test_ml_execution.py tests/test_scenario_ui.py tests/test_scenario_workflow.py tests/test_i18n.py -q`
  - `pdm run python -m compileall src tests scripts`
  - `pdm run pytest -q`
- Observed:
  - targeted registry/ML/UI/workflow suite passed: `45 passed`
  - i18n-aware targeted suite passed: `47 passed`
  - compile succeeded
  - full pytest suite passed: `73 passed`
  - `zh_CN` translation compile reported `468 finished and 0 unfinished`

## Notes

- `anomaly_scores.csv` contains original input rows plus `anomaly_label`, `anomaly_score`, and `anomaly_rank`.
- Higher `anomaly_score` means more anomalous in the exported ranking.
