# Solidify Task

## Input Classification

- Type: `Intent`
- Requested outcome:
  - before implementation, settle the first-wave `P0` scope for legacy-model integration
  - commit the solidified task packet
  - then proceed directly into implementation

## Objective & Hypothesis

- Objective: define the smallest correct `P0` implementation slice that meaningfully reduces model-support gaps without introducing dependency churn beyond the current native runtime stack.
- Hypothesis: the best first wave is a mixed path:
  - unlock `clustering` with `KMeans` and `DBSCAN`
  - strengthen current supervised coverage with `Lasso`, tree, and GBDT families
  - keep `XGBoost`, `LightGBM`, association analysis, and recommendation out of `P0`

## Impact Handshake

### Address and Object

- Task packet:
  - `tasks/model-support-gap/exploration.md`
  - `tasks/model-support-gap/solidify.md`
- Durable technical owners expected in `P0`:
  - `src/xenix/services/storage/models.py`
  - `src/xenix/services/storage/migrations.py`
  - `src/xenix/services/ml/contracts.py`
  - `src/xenix/services/ml/evaluation.py`
  - `src/xenix/services/ml/types.py`
  - `src/xenix/services/ml/registry.py`
  - `src/xenix/services/ml/models/`
  - `src/xenix/services/ml/operations/__init__.py`
  - `src/xenix/services/ml_service.py`
  - `src/xenix/services/ml_task_service.py`
  - `src/xenix/services/scenario_template_service.py`
  - `src/xenix/services/scenario_workflow_service.py`
  - `src/xenix/services/scenario_model_source_service.py`
  - scenario UI surfaces that currently assume supervised prediction/training/inference flow
  - relevant tests under `tests/`

### State Diff

- From:
  - native scenarios advertise `prediction`, `classification`, `clustering`, `anomaly_detection`, and `key_driver_analysis`
  - only supervised `prediction` and `classification` are operational
  - native `ProblemKind` supports only `regression` and `classification`
  - native model registry exposes only 5 supervised models
  - scenario preparation, training, compatible-model reuse, and inference flows assume one target column and supervised evaluation
- To:
  - `P0` adds a first-wave model set:
    - `clustering.kmeans`
    - `clustering.dbscan`
    - `regression.lasso`
    - `regression.decision_tree`
    - `regression.gbdt`
    - `classification.decision_tree`
    - `classification.gbdt`
  - native runtime grows the minimum task/problem-kind support needed for unsupervised clustering
  - native scenario flow can prepare, train, and review clustering outputs without forcing a target column
  - current supervised scenario flow gains broader model choice while staying within `scikit-learn`

### Blast Radius Forecast

- High blast radius:
  - `ProblemKind` enum and all code paths switching on it
  - ML contracts and evaluation-policy ownership
  - model-service base abstractions
  - scenario template semantics around `supervised_required` and `required_target_count`
  - scenario preparation UI and validation
  - training snapshot/result presentation
  - trained-model compatibility filtering
- Medium blast radius:
  - persistence payloads and metadata structure
  - migrations and existing test fixtures
  - translations for scenario copy that currently says `prediction target`
- Low blast radius:
  - existing regression/classification result ranking logic, if left unchanged for supervised models

### Invariants Check

- Keep legacy scripts under `F:\CODING\Project\Xenix\ml` read-only.
- Keep native model services under `src/xenix/services/ml/`.
- Keep parameter schemas shallow and UI-renderable from JSON Schema.
- Keep sequential task execution and current worker lifecycle model.
- Keep existing supervised flows working for:
  - `sales_demand_forecast.v1`
  - `customer_outcome_classification.v1`
- Keep native dependency scope at current `scikit-learn` stack during `P0`.
- Keep association analysis and recommendation outside this first implementation wave.

### Verification

- Static:
  - `python -m compileall src tests scripts`
- Targeted tests to add or update:
  - ML registry coverage for new model keys
  - ML execution coverage for new supervised models
  - clustering task execution coverage
  - scenario workflow coverage for clustering preparation and training run snapshot
  - UI coverage for clustering scenario enablement and non-target preparation rules
- Manual/behavioral anchors:
  - clustering scenario can be opened from the scenario home view
  - clustering data preparation accepts feature-only selection
  - clustering run produces reviewable grouped output
  - supervised training selection still works for prediction/classification

## Current State and Context

- `ScenarioTemplateService` currently hardcodes only supervised templates and uses `required_target_count=1` for both existing templates.
- `MLService._build_training_context()` rejects models that require a target when the work item does not have exactly one target.
- `NumericAndCategoricalModelService` currently assumes:
  - train/evaluate split with a target column
  - holdout persistence containing the target column
  - inference output named `prediction`
- `MLTaskService` currently finalizes only four task kinds:
  - `fit`
  - `hyperparameter_tuning`
  - `evaluate`
  - `inference`
- `ScenarioWorkflowService.prepare_work_item()` currently always validates target-column count against the template.
- `ScenarioModelSourceService` currently infers compatibility from:
  - feature columns
  - target columns
  - expected supervised problem kind from the first template training step
- UI wording across scenario preparation and inference is currently prediction-first and target-first.

## Operation

- `P0` will:
  - introduce the minimum native unsupervised substrate needed for clustering
  - add seven first-wave model services
  - expose a first clustering scenario template and scenario path
  - preserve current supervised behavior
- `P0` will not:
  - add `xgboost` or `lightgbm`
  - add association-analysis or recommendation scenarios
  - fully implement `anomaly_detection`
  - fully implement a standalone `key_driver_analysis` scenario

## Included Scope

- Add new native model-service implementations for:
  - clustering
  - selected regression models
  - selected classification models
- Extend the registry/catalog and UI parameter surfaces.
- Extend problem-kind and task/evaluation semantics enough for clustering.
- Introduce a clustering scenario template and wire it into the scenario flow.
- Adapt scenario preparation, training, and result display for feature-only clustering setup.
- Add or update tests needed to bound the new behavior.

## Excluded Scope

- External runtime dependencies:
  - `xgboost`
  - `lightgbm`
  - `mlxtend`
  - `apyori`
- New home-surface scenario families for:
  - association analysis
  - recommendations
- Dedicated anomaly-scoring semantics.
- Fully independent `key_driver_analysis` scenario UX.
- Broad technical-workspace redesign outside the scenario-first path.

## First-Wave Model Set

### Clustering

- `clustering.kmeans`
- `clustering.dbscan`

### Regression

- `regression.lasso`
- `regression.decision_tree`
- `regression.gbdt`

### Classification

- `classification.decision_tree`
- `classification.gbdt`

## Likely Affected Files

- `src/xenix/services/storage/models.py`
- `src/xenix/services/storage/migrations.py`
- `src/xenix/services/ml/contracts.py`
- `src/xenix/services/ml/evaluation.py`
- `src/xenix/services/ml/types.py`
- `src/xenix/services/ml/registry.py`
- `src/xenix/services/ml/models/base.py`
- `src/xenix/services/ml/models/regression.py`
- `src/xenix/services/ml/models/classification.py`
- new clustering model module under `src/xenix/services/ml/models/`
- `src/xenix/services/ml/models/__init__.py`
- `src/xenix/services/ml_service.py`
- `src/xenix/services/ml_task_service.py`
- `src/xenix/services/scenario_template_service.py`
- `src/xenix/services/analysis_scenario_service.py`
- `src/xenix/services/scenario_workflow_service.py`
- `src/xenix/services/scenario_model_source_service.py`
- `src/xenix/ui/scenario_data_preparation_dialog.py`
- `src/xenix/ui/scenario_training_selection_dialog.py`
- `src/xenix/ui/scenario_training_dialog.py`
- `src/xenix/ui/scenario_inference_dialog.py`
- `src/xenix/ui/analysis_scenario_text.py`
- `src/xenix/ui/scenario_template_text.py`
- `src/xenix/ui/widgets/column_selection.py`
- `src/xenix/translations/xenix_en_US.ts`
- `src/xenix/translations/xenix_zh_CN.ts`
- `tests/test_ml_registry.py`
- `tests/test_ml_execution.py`
- `tests/test_scenario_workflow.py`
- `tests/test_scenario_ui.py`

## Main Risks

- Unsupervised support can sprawl if `P0` tries to force clustering into the exact supervised lifecycle without a narrow contract.
- Reusing current inference semantics for clustering may create confusing UX if the output remains prediction-shaped.
- Compatibility logic for trained-model reuse may need a clustering-specific rule instead of current feature+target equality.
- Existing UI copy and validation are prediction-first, so clustering may feel broken unless wording and enablement rules are updated together.

## Smallest Resolved Decisions

- `P0` optimization target: mixed path
- first-wave models:
  - `KMeans`
  - `DBSCAN`
  - `Lasso`
  - regression/classification `DecisionTree`
  - regression/classification `GBDT`
- dependency policy:
  - stay inside current `scikit-learn` runtime
- deferred families:
  - association analysis
  - recommendations
  - `XGBoost`
  - `LightGBM`

## Plan for Execute Mode

1. Extend core ML/storage contracts for a narrow clustering problem kind.
2. Implement the first-wave model services and registry updates.
3. Add a clustering scenario template and adapt scenario preparation/training flow.
4. Adjust UI wording, validation, and result presentation where target-first assumptions break.
5. Add and run targeted verification for registry, execution, workflow, and scenario UI.

## Confirmation State

- User confirmed the mixed-path assumption set and authorized:
  - solidify first
  - create a commit
  - proceed directly into implementation
