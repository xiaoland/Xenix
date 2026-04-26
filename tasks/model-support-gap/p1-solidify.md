# P1 Solidify Task

## Input Classification

- Type: `Intent`
- Requested outcome:
  - continue the model-support expansion after `P0`
  - focus the next implementation wave on supervised model breadth
  - keep implementation paused until explicit `start`

## Objective & Hypothesis

- Objective: define the smallest correct `P1` implementation slice for adding low-risk supervised model coverage inside the current native ML architecture.
- Hypothesis: `P1` should stay inside the existing `scikit-learn` dependency boundary and extend only regression/classification model services, registry entries, and tests.

## Address and Object

- Task packet:
  - `tasks/model-support-gap/p1-solidify.md`
- Durable technical owners expected in `P1`:
  - `src/xenix/services/ml/models/regression.py`
  - `src/xenix/services/ml/models/classification.py`
  - `src/xenix/services/ml/models/__init__.py`
  - `src/xenix/services/ml/registry.py`
  - `tests/test_ml_registry.py`
  - `tests/test_ml_execution.py`
  - possibly `tests/test_scenario_ui.py` if model-selection UI count/order assertions need adjustment

## State Diff

- From:
  - native catalog has 12 models after `P0`
  - prediction/classification scenarios can already choose from the expanded first-wave supervised catalog
  - remaining low-risk legacy supervised models are still absent from the native registry
- To:
  - native catalog includes the next supervised breadth pack
  - prediction/classification model selection gains more model families while preserving the same training/evaluate/inference contract
  - no dependency, storage, problem-kind, or task-lifecycle expansion is required

## P1 Model Set

### Regression

- `regression.bayesian_ridge`
- `regression.knn`
- `regression.ada_boost`
- `regression.polynomial`

### Classification

- `classification.naive_bayes`
- `classification.knn`
- `classification.ada_boost`

## Source Mapping

- Legacy sources under `F:\CODING\Project\Xenix\ml`:
  - `regression/bayesian_ridge_regression/bayesian_ridge_regression.py`
  - `regression/k_nearest_neighbors/k_nearest_neighbors.py`
  - `regression/ada_boost/ada_boost.py`
  - `regression/polynomial_regression/polynomial_regression.py`
  - `classification/naive_bayes_model/naive_bayes_model.py`
  - `classification/k_nearest_neighbors_classification_model/k_nearest_neighbors_classification_model.py`
  - `classification/ada_boost_classification_model/ada_boost_classification_model.py`
- Native target:
  - implement idiomatic native model services under `src/xenix/services/ml/models/`
  - preserve legacy scripts as read-only reference material

## Blast Radius Forecast

- Low blast radius:
  - model service classes and Pydantic schemas
  - registry exports and catalog ordering
  - tests that assert catalog size or available model count
- Medium blast radius:
  - model-selection UI if more compatible models affect assumptions around default visible cards
  - polynomial regression if implemented as a pipeline stage rather than a plain estimator
- Stable surfaces:
  - `ProblemKind`
  - `MLTaskType`
  - evaluation policies
  - work item preparation
  - clustering lifecycle
  - inference output contract

## Invariants Check

- Keep legacy `ml/` scripts read-only.
- Keep dependency scope inside existing `scikit-learn`.
- Keep parameter schemas shallow and JSON Schema form-renderable.
- Keep supervised models on the existing `NumericAndCategoricalModelService` path where possible.
- Keep current scenario templates and defaults stable unless adding model visibility requires tests to acknowledge the larger catalog.
- Keep `xgboost`, `lightgbm`, association analysis, and recommendation out of `P1`.

## Design Notes

- `BayesianRidge`, `KNeighborsRegressor`, `AdaBoostRegressor`, `GaussianNB`, `KNeighborsClassifier`, and `AdaBoostClassifier` can fit the existing supervised service pattern.
- `PolynomialRegression` likely needs a small native service subclass or estimator pipeline because the polynomial feature expansion belongs before the final linear estimator.
- KNN models benefit from numeric scaling; keep `scaler_for_numeric=True`.
- Naive Bayes should use `GaussianNB` as the simplest native fit for mixed numeric/categorical preprocessing output.
- AdaBoost should expose shallow, bounded schemas such as `n_estimators` and `learning_rate`.

## Verification

- Static:
  - `pdm run python -m compileall src tests scripts`
- Targeted:
  - `pdm run pytest tests/test_ml_registry.py tests/test_ml_execution.py -q`
- Full:
  - `pdm run pytest -q`
- Behavioral anchors:
  - catalog exposes all `P1` model keys
  - each new model has a valid `param_schema`
  - tunable models expose a valid `param_grid_schema`
  - at least one new regression model can complete fit/evaluate
  - at least one new classification model can complete tune/evaluate
  - existing `P0` clustering tests keep passing

## Deferred After P1

- `P2` dependency-heavy tabular models:
  - `regression.xgboost`
  - `regression.light_gbm`
  - `classification.xgboost`
  - `classification.light_gbm`
- Scenario/reporting work:
  - key-driver analysis scenario UX
  - cluster profiling and visualization
  - anomaly scoring semantics
  - association analysis and recommendation scenario families

## Confirmation State

- User agreed with the recommended `P1 supervised model pack`.
- User authorized implementation after reviewing the scope.
