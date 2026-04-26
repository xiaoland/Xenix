# Key Driver Analysis V1 Solidify Task

## Input Classification

- Type: `Intent`
- Requested outcome:
  - make the planned `Key Driver Analysis` scenario usable
  - reuse the existing scenario, ML task, trained-model, and artifact infrastructure
  - keep the first version inside current `scikit-learn` dependency scope

## Objective & Hypothesis

- Objective: enable a guided scenario that ranks business input columns by their influence on a supervised target and exports an openable key-driver report.
- Hypothesis: `Key Driver Analysis V1` can be delivered by adding a supervised analysis template, producing feature-importance artifacts during supported fit/tune tasks, and routing the scenario to training results rather than prediction inference.

## Address and Object

- Task packet:
  - `tasks/model-support-gap/key-driver-analysis-v1-solidify.md`
- Durable owners expected in this slice:
  - `src/xenix/services/analysis_scenario_service.py`
  - `src/xenix/services/scenario_template_service.py`
  - `src/xenix/services/ml/models/base.py`
  - `src/xenix/ui/main_window.py`
  - `src/xenix/ui/scenario_template_text.py`
  - `src/xenix/ui/scenario_training_dialog.py`
  - `src/xenix/translations/xenix_en_US.ts`
  - `src/xenix/translations/xenix_zh_CN.ts`
  - `tests/test_ml_execution.py`
  - `tests/test_scenario_ui.py`
  - `tests/test_scenario_workflow.py`
  - `tests/test_i18n.py`

## State Diff

- From:
  - `key_driver_analysis` exists as a home-card concept but remains planned and unclickable
  - scenario templates cover prediction, classification, and clustering
  - supervised training saves models and evaluation metrics but does not export driver rankings
  - supervised scenario completion routes toward prediction inference
- To:
  - `key_driver_analysis` is available from the home view
  - a new `key_driver_analysis.v1` template prepares supervised data and trains explanation-friendly models
  - supported supervised fit/tune tasks can export `key_drivers.csv`
  - key-driver runs end at the training dashboard with openable report artifacts

## Scope

- Add `key_driver_analysis.v1` template:
  - one target column
  - one or more input columns
  - curated regression-oriented plan for numeric business outcomes
  - default plan centered on feature-importance-friendly models
- Enable `key_driver_analysis` in `AnalysisScenarioService` by linking it to the new template.
- Add a template-level behavior flag for post-training prediction:
  - prediction/classification continue to inference
  - clustering and key-driver analysis close results after terminal output review
- Add key-driver report generation for supported supervised model pipelines:
  - tree models via `feature_importances_`
  - linear models via absolute coefficients where feature counts align
  - aggregate one-hot encoded categorical terms back to source input columns
  - write `key_drivers.csv`
  - include compact top-driver summary in task result payload
- Improve training dashboard copy for key-driver outputs.

## Out of Scope

- Classification-specific key-driver template selection.
- SHAP or external explainability dependencies.
- Charts.
- Natural-language narrative generation.
- Persisted storage schema changes.
- Changes to legacy scripts under `F:\CODING\Project\Xenix\ml`.
- `Clustering Profile V1.5`.

## Blast Radius Forecast

- Low blast radius:
  - analysis scenario availability
  - template catalog and localized template text
  - key-driver CSV artifact for supported supervised model outputs
- Medium blast radius:
  - supervised result summaries now may contain non-metric report metadata
  - training dashboard needs to distinguish prediction, clustering, and supervised analysis flows
  - tests that assume all supervised templates continue to prediction
- Stable surfaces:
  - `ProblemKind`
  - `MLTaskType`
  - SQLite schema
  - worker execution model
  - inference history

## Invariants Check

- Keep existing prediction/classification inference flow unchanged.
- Keep clustering behavior unchanged.
- Keep model parameter schemas shallow and JSON Schema form-renderable.
- Keep report generation best-effort for models without compatible importance attributes.
- Keep generated reports CSV-readable by spreadsheet tools.
- Keep all existing P1.5 model-selection improvements available.

## Verification

- Static:
  - `pdm run python -m compileall src tests scripts`
- Targeted:
  - `pdm run pytest tests/test_ml_execution.py tests/test_scenario_ui.py tests/test_scenario_workflow.py tests/test_i18n.py -q`
- Full:
  - `pdm run pytest -q`
- Behavioral anchors:
  - home key-driver card is enabled
  - key-driver card opens data preparation for `key_driver_analysis.v1`
  - prepared key-driver run routes directly to training selection
  - supported trained model writes `key_drivers.csv`
  - training dashboard exposes the openable output CSV
  - prediction/classification continue-to-prediction tests keep passing

## Confirmation State

- User explicitly requested: `让我们开始补充 Key Driver Analysis 吧`.
- Implementation authorized.
