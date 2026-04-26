# P1 Execution Task

## Objective & Hypothesis

- Objective: implement the `P1 supervised model pack` defined in `p1-solidify.md`.
- Hypothesis: the existing supervised training/evaluate/inference lifecycle can absorb the P1 models through native model-service classes, registry wiring, and focused tests.

## Scope Executed

- Added regression model services:
  - `regression.bayesian_ridge`
  - `regression.knn`
  - `regression.ada_boost`
  - `regression.polynomial`
- Added classification model services:
  - `classification.naive_bayes`
  - `classification.knn`
  - `classification.ada_boost`
- Added a dense-preprocessing switch to the supervised base service for estimators that require dense arrays.
- Kept storage, problem-kind, task lifecycle, evaluation policies, scenario templates, and clustering flow unchanged.

## Guardrails Touched

- Legacy `F:\CODING\Project\Xenix\ml` scripts stayed read-only.
- Runtime dependency scope stayed inside existing `scikit-learn`.
- Parameter schemas stayed shallow and JSON Schema form-renderable.
- P1 changes stayed within native supervised model services, registry, and tests.
- Existing P0 clustering behavior stayed covered by the full test suite.

## Verification

- Command:
  - `pdm run pytest tests/test_ml_registry.py tests/test_ml_execution.py -q`
  - `pdm run python -m compileall src tests scripts`
  - `pdm run pytest -q`
- Observed:
  - targeted registry/execution suite passed: `11 passed`
  - compile succeeded
  - full pytest suite passed: `62 passed`

## Notes

- `PolynomialRegressionService` uses a custom supervised pipeline with `PolynomialFeatures` before `LinearRegression`.
- `NaiveBayesClassificationService` and `BayesianRidgeRegressionService` use dense preprocessing to avoid sparse matrix incompatibility.
- AdaBoost services expose `estimator_max_depth` as a UI-friendly shallow schema and map it into the nested sklearn estimator parameter internally.
