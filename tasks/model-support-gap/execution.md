# Execution Task

## Objective & Hypothesis

- Objective: implement `P0` of the native model-support expansion by adding the first clustering substrate plus the selected first-wave supervised models.
- Hypothesis: the smallest correct path is to introduce a narrow clustering-specific lifecycle while preserving the current supervised training/evaluate/inference flow for regression and classification.

## Pre-Execution Restatement

- Target:
  - add `clustering` as a first native unsupervised problem kind
  - add `KMeans`, `DBSCAN`, `Lasso`, regression/classification `DecisionTree`, and regression/classification `GBDT`
  - wire a clustering template into the scenario-first flow
- Current state and context:
  - the repository is stable for supervised prediction/classification scenarios only
  - the task packet for this workstream was committed as `176d951`
- Operation:
  - mutate only native ML, scenario, UI, storage, and test owners needed for `P0`
- Scope included:
  - model registry expansion
  - clustering-specific task/result support
  - clustering scenario preparation/training/result path
  - targeted UI copy and validation updates
  - targeted tests
- Scope excluded:
  - external ML dependencies
  - association analysis
  - recommendations
  - dedicated anomaly-detection scoring
  - standalone key-driver-analysis scenario
- Invariants:
  - legacy `ml/` stays untouched
  - supervised scenario behavior remains working
  - `scikit-learn` remains the runtime dependency boundary
  - parameter schemas remain shallow and form-renderable
- Likely affected files:
  - see `tasks/model-support-gap/solidify.md`
- Uncertainty:
  - exact UI shape for clustering results versus reuse of the current inference-first surface
  - exact minimum compatibility rule for clustering-trained model reuse

## Guardrails Touched

- Keep changes inside durable owners only.
- Keep the task packet aligned with the actual implementation.
- Prefer the smallest clustering contract that does not degrade current supervised behavior.

## Plan

1. Extend storage/contracts/evaluation/types for a narrow clustering problem kind.
2. Implement first-wave model services and registry wiring.
3. Add clustering template and adapt scenario workflow for feature-only preparation and training.
4. Update UI text, validation, and result presentation where supervised assumptions break.
5. Add and run targeted verification.

## Verification

- Command:
  - `pdm run python -m compileall src tests scripts`
  - `pdm run pytest tests/test_ml_registry.py tests/test_ml_execution.py tests/test_scenario_workflow.py tests/test_scenario_ui.py -q`
  - `pdm run pytest -q`
- Expected:
  - clustering scenario path becomes operable
  - first-wave supervised models become selectable and executable
  - existing supervised scenario tests keep passing
- Observed:
  - added native `ProblemKind.CLUSTERING` with a narrow fit-only lifecycle and export artifact support
  - added `clustering.kmeans` and `clustering.dbscan`
  - added `regression.lasso`, `regression.decision_tree`, `regression.gradient_boosting`
  - added `classification.decision_tree`, `classification.gradient_boosting`
  - enabled `clustering` in scenario-first mode with `customer_segmentation_clustering.v1`
  - feature-only preparation now bypasses model-source selection and routes directly into training selection
  - clustering training finishes without inference gating and surfaces saved-output summaries in the training dashboard
  - clustering training dashboard now exposes the selected step's `cluster_assignments.csv` artifact through an `Open Output CSV` action
  - the new output action is translated and compiled into the runtime `.qm` files
  - targeted regression tests added for registry, execution, workflow, and UI coverage
  - compile succeeded
  - targeted pytest suite passed: `31 passed`
  - follow-up UI artifact test passed
  - full pytest suite passed: `60 passed`

## Promotion Notes

- Durable truth candidates:
  - narrow native clustering lifecycle
  - first-wave model catalog expansion
- Keep in task only:
  - sequencing notes
  - intermediate tradeoffs while converging the UI/result path
