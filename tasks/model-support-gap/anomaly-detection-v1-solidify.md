# Anomaly Detection V1 Solidify Task

## Input Classification

- Type: `Intent`
- Requested outcome:
  - make the planned `Anomaly Detection` scenario usable
  - reuse current feature-only scenario and ML task infrastructure
  - stay inside the existing `scikit-learn` dependency scope

## Objective & Hypothesis

- Objective: enable a guided feature-only scenario that scores unusual rows and exports an openable anomaly report.
- Hypothesis: `Anomaly Detection V1` can be delivered by adding an anomaly problem kind, two native unsupervised anomaly model services, a scenario template, and training-dashboard output handling.

## Address and Object

- Task packet:
  - `tasks/model-support-gap/anomaly-detection-v1-solidify.md`
- Durable owners expected in this slice:
  - `src/xenix/services/storage/models.py`
  - `src/xenix/services/ml/evaluation.py`
  - `src/xenix/services/ml/models/base.py`
  - `src/xenix/services/ml/models/anomaly.py`
  - `src/xenix/services/ml/registry.py`
  - `src/xenix/services/analysis_scenario_service.py`
  - `src/xenix/services/scenario_template_service.py`
  - `src/xenix/ui/scenario_template_text.py`
  - `src/xenix/ui/scenario_training_dialog.py`
  - `src/xenix/translations/xenix_en_US.ts`
  - `src/xenix/translations/xenix_zh_CN.ts`
  - `tests/test_ml_registry.py`
  - `tests/test_ml_execution.py`
  - `tests/test_scenario_ui.py`
  - `tests/test_scenario_workflow.py`
  - `tests/test_i18n.py`

## State Diff

- From:
  - `anomaly_detection` exists as a home-card concept but remains planned and unclickable
  - native model catalog has regression, classification, and clustering problem kinds
  - feature-only output workflow is proven by clustering
- To:
  - `anomaly_detection` is available from the home view
  - `anomaly_detection.v1` prepares feature-only data and trains anomaly models
  - anomaly fit tasks export `anomaly_scores.csv`
  - training dashboard surfaces anomaly count, anomaly rate, and openable output CSV

## Scope

- Add `ProblemKind.ANOMALY_DETECTION`.
- Add default evaluation policy metadata for anomaly detection without split/evaluate.
- Add native anomaly model services:
  - `anomaly.isolation_forest`
  - `anomaly.local_outlier_factor`
- Add `anomaly_detection.v1` scenario template:
  - one or more input columns
  - no target column
  - no inference continuation
- Generate anomaly output artifact:
  - file name: `anomaly_scores.csv`
  - original columns plus `anomaly_label`, `anomaly_score`, and `anomaly_rank`
  - result summary: row count, anomaly count, anomaly rate, score/label column names
- Update training dashboard copy and card summaries for anomaly outputs.

## Out of Scope

- Supervised anomaly detection.
- Time-series anomaly detection.
- Threshold editing UI.
- Charts.
- New dependencies.
- Storage schema migrations beyond enum extension.
- Changes to legacy scripts under `F:\CODING\Project\Xenix\ml`.
- `Clustering Profile V1.5`.

## Blast Radius Forecast

- Low blast radius:
  - model registry count and catalog tests
  - scenario home availability
  - feature-only route reuse
- Medium blast radius:
  - `ProblemKind` enum expansion
  - training dashboard branches for multiple feature-only output scenarios
  - result-summary display logic
- Stable surfaces:
  - `MLTaskType`
  - SQLite table structure
  - prediction/classification inference flow
  - clustering assignments output
  - key-driver output flow

## Invariants Check

- Keep anomaly detection feature-only.
- Keep no evaluation or inference gate for anomaly V1.
- Keep output CSV spreadsheet-readable.
- Keep model parameter schemas shallow and JSON Schema form-renderable.
- Keep all existing scenario tests passing.

## Verification

- Static:
  - `pdm run python -m compileall src tests scripts`
- Targeted:
  - `pdm run pytest tests/test_ml_registry.py tests/test_ml_execution.py tests/test_scenario_ui.py tests/test_scenario_workflow.py tests/test_i18n.py -q`
- Full:
  - `pdm run pytest -q`
- Behavioral anchors:
  - home anomaly card is enabled
  - anomaly card opens data preparation for `anomaly_detection.v1`
  - prepared anomaly run routes directly to training selection
  - anomaly fit writes `anomaly_scores.csv`
  - training dashboard can open anomaly output artifacts
  - clustering and key-driver output flows remain intact

## Confirmation State

- User explicitly requested: `接下来让我们补上 Anomaly Detection`.
- Implementation authorized.
