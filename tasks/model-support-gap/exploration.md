# Exploration Task

## Objective & Hypothesis

- Objective: map which legacy models under `F:\CODING\Project\Xenix\ml` should be integrated into Xenix Native based on the scenarios currently described in the native app and the model coverage already present in the native ML registry.
- Hypothesis: Xenix Native currently covers only a narrow supervised subset. The most important gaps are:
  - clustering models needed to unlock the planned `clustering` scenario
  - additional `scikit-learn` supervised models that expand `prediction` and `classification`
  - a small explainability-oriented subset that can support `key_driver_analysis`

## Prompt

- The product currently exposes several analysis scenarios, but many of them remain unavailable because the supporting models are not yet integrated.
- Analyze the current native scenario descriptions and compare them against the legacy model inventory under `F:\CODING\Project\Xenix\ml`.
- Produce a recommendation that distinguishes:
  - direct fit to the current scenario catalog
  - direct fit to the current native ML architecture
  - models blocked by missing task/problem-kind support
  - models better treated as future scenarios rather than immediate gaps

## Guardrails Touched

- Current work stays in Mode A exploration only.
- No production code, durable docs, packaging config, or dependency graph changes.
- Current reasoning stays under `tasks/model-support-gap/`.
- Recommendations should follow current scenario semantics before introducing new scenario families.
- Dependency-sensitive models must be called out explicitly before any implementation.

## Current Facts

- Native scenario registry currently exposes five scenario keys:
  - `prediction`
  - `classification`
  - `clustering`
  - `anomaly_detection`
  - `key_driver_analysis`
- Native availability state currently marks only `prediction` and `classification` as available.
- Native scenario templates currently exist only for:
  - `sales_demand_forecast.v1`
  - `customer_outcome_classification.v1`
- Native ML registry currently contains only five models:
  - `regression.linear`
  - `regression.ridge`
  - `regression.random_forest`
  - `classification.logistic_regression`
  - `classification.random_forest`
- Native durable `ProblemKind` currently contains only:
  - `regression`
  - `classification`
- Native evaluation policy coverage currently exists only for:
  - regression metrics and ranking
  - classification metrics and ranking
- Native runtime dependencies currently include `scikit-learn`, `pandas`, `openpyxl`, `joblib`, and do not yet include:
  - `xgboost`
  - `lightgbm`
  - `mlxtend`
  - `apyori`
- Legacy model inventory under `F:\CODING\Project\Xenix\ml` is grouped into:
  - `regression`
  - `classification`
  - `clustering_and_segmentation`
  - `association_analysis`
  - `recommendations`
- Legacy regression comparison scripts enumerate twelve regression models in total. Native has already absorbed three of them.
- Legacy classification comparison scripts enumerate nine classification models in total. Native has already absorbed two of them.
- Legacy clustering inventory currently contains two concrete clustering scripts:
  - `customer_information_kmeans.py`
  - `stock_customer_dbscan.py`
- Legacy inventory does not contain a dedicated anomaly-detection script family. The nearest available primitive is DBSCAN noise labeling.
- Legacy association-analysis and recommendation scripts describe additional analytical surfaces that are not yet first-class scenarios in the native home flow.

## Constraints Observed

- Current native training and evaluation contracts are centered on supervised learning with holdout evaluation.
- Current model-service base implementation for the active models assumes exactly one target column during fit/evaluate flow.
- `clustering`, `anomaly_detection`, and part of `key_driver_analysis` need either:
  - a new `ProblemKind`, or
  - a parallel unsupervised task lifecycle
- `xgboost` and `lightgbm` models are technically attractive, but they require dependency, packaging, and smoke-test expansion.
- `association_analysis` and `recommendations` are not a clean semantic match for the current five-scenario home surface.

## Scenario-to-Model Gap Map

### Prediction

- Legacy models that fit the current prediction scenario and current native architecture with relatively low conceptual risk:
  - `regression/lasso/lasso.py`
  - `regression/bayesian_ridge_regression/bayesian_ridge_regression.py`
  - `regression/k_nearest_neighbors/k_nearest_neighbors.py`
  - `regression/regression_decision_tree/regression_decision_tree.py`
  - `regression/gbdt/gbdt.py`
  - `regression/ada_boost/ada_boost.py`
  - `regression/polynomial_regression/polynomial_regression.py`
- Legacy models that fit prediction but add dependency and packaging cost:
  - `regression/xgboost/xgboost.py`
  - `regression/light_gbm/light_gbm.py`

### Classification

- Legacy models that fit the current classification scenario and current native architecture with relatively low conceptual risk:
  - `classification/classification_decision_tree/classification_decision_tree.py`
  - `classification/naive_bayes_model/naive_bayes_model.py`
  - `classification/k_nearest_neighbors_classification_model/k_nearest_neighbors_classification_model.py`
  - `classification/gbdt_classification_model/gbdt_classification_model.py`
  - `classification/ada_boost_classification_model/ada_boost_classification_model.py`
- Legacy models that fit classification but add dependency and packaging cost:
  - `classification/xgboost_classification_model/xgboost_classification_model.py`
  - `classification/light_gbm_classification_model/light_gbm_classification_model.py`

### Clustering

- Legacy models that directly match the current clustering scenario description:
  - `clustering_and_segmentation/customer_information_kmeans.py`
  - `clustering_and_segmentation/stock_customer_dbscan.py`
- `KMeans` is the clearest V1 segmentation model because it gives stable labeled segments.
- `DBSCAN` is the clearest complement because it naturally marks dense clusters and noise points.
- Both models are blocked by native architecture gaps around unsupervised problem-kind support, evaluation, artifact semantics, and scenario template flow.

### Anomaly Detection

- No dedicated anomaly-detection family currently exists in the legacy `ml` inventory.
- The closest available bootstrap path is `DBSCAN` noise labeling from `stock_customer_dbscan.py`.
- A native `anomaly_detection` scenario would still need explicit product semantics for:
  - anomaly score or severity
  - abnormal-row ranking
  - result explanation language

### Key Driver Analysis

- The strongest legacy candidates for a V1 key-driver path are models that expose interpretable coefficients or feature importance:
  - `regression/lasso/lasso.py`
  - `regression/regression_decision_tree/regression_decision_tree.py`
  - `regression/gbdt/gbdt.py`
  - `classification/classification_decision_tree/classification_decision_tree.py`
  - `classification/gbdt_classification_model/gbdt_classification_model.py`
- `Lasso` is especially useful because sparse coefficients align well with driver ranking and direction-of-impact language.
- Tree and boosting models are useful because they expose feature-importance summaries and can support rule-like explanations.

### Not Directly Mapped to Current Home Scenarios

- `association_analysis/apyori_cross_sell.py`
- `association_analysis/mlxtend_cross_sell.py`
- `recommendations/movie_recommendations.py`
- These scripts represent valid future product surfaces, but they do not directly close the current gap between the existing native home scenarios and the currently available native model catalog.

## Recommended Integration Backlog

### P0: direct scenario unlock or highest leverage

- `clustering_and_segmentation/customer_information_kmeans.py`
- `clustering_and_segmentation/stock_customer_dbscan.py`
- `regression/lasso/lasso.py`
- `regression/regression_decision_tree/regression_decision_tree.py`
- `regression/gbdt/gbdt.py`
- `classification/classification_decision_tree/classification_decision_tree.py`
- `classification/gbdt_classification_model/gbdt_classification_model.py`

### P1: supervised breadth inside current architecture

- `regression/bayesian_ridge_regression/bayesian_ridge_regression.py`
- `regression/k_nearest_neighbors/k_nearest_neighbors.py`
- `regression/ada_boost/ada_boost.py`
- `regression/polynomial_regression/polynomial_regression.py`
- `classification/naive_bayes_model/naive_bayes_model.py`
- `classification/k_nearest_neighbors_classification_model/k_nearest_neighbors_classification_model.py`
- `classification/ada_boost_classification_model/ada_boost_classification_model.py`

### P2: stronger tabular models with dependency expansion

- `regression/xgboost/xgboost.py`
- `regression/light_gbm/light_gbm.py`
- `classification/xgboost_classification_model/xgboost_classification_model.py`
- `classification/light_gbm_classification_model/light_gbm_classification_model.py`

### Defer until product adds new scenario families

- `association_analysis/apyori_cross_sell.py`
- `association_analysis/mlxtend_cross_sell.py`
- `recommendations/movie_recommendations.py`

## Unknowns

- Should near-term priority optimize for unlocking new scenario cards or for broadening model choice inside the already-available `prediction` and `classification` flows?
- Should `anomaly_detection` be bootstrapped from `DBSCAN` noise output, or should it wait for a dedicated anomaly model family?
- Does `key_driver_analysis` want a full standalone scenario, or a reporting layer built on top of existing supervised models?
- Are new native dependencies acceptable in the near term?
- Should association analysis and recommendation remain outside the home surface, or are they candidates for future scenario expansion?

## Candidate Paths

1. Scenario-unlock-first path
   - extend native problem-kind/task support for unsupervised work
   - integrate `KMeans` and `DBSCAN`
   - use `Lasso` plus tree/boosting importance as the first `key_driver_analysis` substrate
2. Supervised-breadth-first path
   - stay inside the current supervised architecture
   - integrate missing `scikit-learn` regression/classification models first
   - postpone clustering and anomaly support until after the supervised catalog is broader
3. Mixed path
   - treat `KMeans`, `DBSCAN`, `Lasso`, and decision-tree / GBDT families as the first wave
   - postpone dependency-heavy models and non-mapped scenario families to later packets

## Verification Anchors

- Native scenario registry and availability state
- Native scenario template inventory
- Native model registry
- Native `ProblemKind` and evaluation-policy coverage
- Native dependency list in `pyproject.toml`
- Legacy regression comparison inventory
- Legacy classification comparison inventory
- Legacy clustering scripts
- Legacy association-analysis and recommendation scripts

## Smallest Confirmation Needed

- Confirm which optimization target should drive the first implementation wave:
  - unlock `clustering` / `anomaly_detection` / `key_driver_analysis`
  - broaden `prediction` / `classification`
  - run the mixed path
- Confirm whether adding external runtime dependencies is acceptable for the native package in the next wave.

## Promotion Candidate Truths

- Leave empty until implementation priority is confirmed.
