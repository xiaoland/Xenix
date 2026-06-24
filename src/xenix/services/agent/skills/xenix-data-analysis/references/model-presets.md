# Model Presets for `model.train`, `model.hyper_train`, and `model.apply`

Use this file before invoking model tools. These presets are conceptual parameters. Adapt names to the exact schema supported by Xenix model tools.

## Universal modeling rules

1. Train a simple baseline first.
2. Tune only after the baseline is valid and the business question needs better predictive performance.
3. Exclude leakage fields, identifiers, post-outcome fields, and sensitive fields that should not drive decisions.
4. Use a fixed random seed when supported.
5. For classification with imbalance, request stratified split and class-aware metrics.
6. For regression, translate errors into business units.
7. Request feature importance or model explanation only when the model tool supports it.
8. Use `model.apply` for scored lists, probabilities, and batch predictions.

## Default split policy

Classification:

```json
{
  "split": {
    "method": "train_test",
    "test_size": 0.2,
    "stratify": true,
    "random_seed": 42
  }
}
```

Regression:

```json
{
  "split": {
    "method": "train_test",
    "test_size": 0.2,
    "random_seed": 42
  }
}
```

If the dataset is time-ordered and prediction is for the future, prefer a time-based split instead of random split.

## Classification baseline presets

### Logistic regression: interpretable baseline

Use when the target is binary or low-cardinality categorical and interpretability matters.

```json
{
  "model_family": "logistic_regression",
  "preprocessing": {
    "numeric": "standardize",
    "categorical": "one_hot",
    "missing": "impute"
  },
  "params": {
    "penalty": "l2",
    "C": 1.0,
    "class_weight": "auto_if_imbalanced",
    "max_iter": 1000,
    "random_seed": 42
  },
  "metrics": ["confusion_matrix", "accuracy", "precision", "recall", "f1", "auc"]
}
```

Small tune grid:

```json
{
  "C": [0.1, 1.0, 10.0],
  "class_weight": [null, "balanced"]
}
```

### Tree-based classifier: nonlinear baseline

Use when interactions or nonlinear boundaries are plausible.

```json
{
  "model_family": "random_forest_classifier",
  "params": {
    "n_estimators": 300,
    "max_depth": null,
    "min_samples_leaf": 5,
    "max_features": "sqrt",
    "random_seed": 42
  },
  "metrics": ["confusion_matrix", "accuracy", "precision", "recall", "f1", "auc"]
}
```

Small tune grid:

```json
{
  "n_estimators": [200, 500],
  "max_depth": [5, 10, 20, null],
  "min_samples_leaf": [1, 5, 10],
  "max_features": ["sqrt", 0.5]
}
```

### Gradient boosting classifier: performance candidate

Use when the dataset is medium-sized, tabular, and baseline is not sufficient.

```json
{
  "model_family": "gradient_boosting_classifier",
  "params": {
    "learning_rate": 0.05,
    "n_estimators": 300,
    "max_depth": 3,
    "random_seed": 42
  },
  "metrics": ["confusion_matrix", "accuracy", "precision", "recall", "f1", "auc"]
}
```

Small tune grid:

```json
{
  "learning_rate": [0.03, 0.05, 0.1],
  "n_estimators": [100, 300, 500],
  "max_depth": [2, 3, 5]
}
```

## Regression baseline presets

### Linear or ridge regression: interpretable baseline

```json
{
  "model_family": "ridge_regression",
  "preprocessing": {
    "numeric": "standardize",
    "categorical": "one_hot",
    "missing": "impute"
  },
  "params": {
    "alpha": 1.0,
    "random_seed": 42
  },
  "metrics": ["mae", "rmse", "r2"]
}
```

Small tune grid:

```json
{
  "alpha": [0.1, 1.0, 10.0, 100.0]
}
```

### Random forest regressor: nonlinear baseline

```json
{
  "model_family": "random_forest_regressor",
  "params": {
    "n_estimators": 300,
    "max_depth": null,
    "min_samples_leaf": 5,
    "max_features": 0.8,
    "random_seed": 42
  },
  "metrics": ["mae", "rmse", "r2"]
}
```

Small tune grid:

```json
{
  "n_estimators": [200, 500],
  "max_depth": [5, 10, 20, null],
  "min_samples_leaf": [1, 5, 10],
  "max_features": [0.6, 0.8, 1.0]
}
```

### Gradient boosting regressor: performance candidate

```json
{
  "model_family": "gradient_boosting_regressor",
  "params": {
    "learning_rate": 0.05,
    "n_estimators": 300,
    "max_depth": 3,
    "random_seed": 42
  },
  "metrics": ["mae", "rmse", "r2"]
}
```

## Neural-network presets

Use only after an interpretable baseline exists. Read `references/neural-network.md` first.

Classification:

```json
{
  "model_family": "mlp_classifier",
  "preprocessing": {
    "numeric": "standardize",
    "categorical": "one_hot",
    "missing": "impute"
  },
  "params": {
    "hidden_layer_sizes": [64, 32],
    "activation": "relu",
    "alpha": 0.001,
    "learning_rate_init": 0.001,
    "max_iter": 300,
    "early_stopping": true,
    "random_seed": 42
  },
  "metrics": ["confusion_matrix", "accuracy", "precision", "recall", "f1", "auc"]
}
```

Regression:

```json
{
  "model_family": "mlp_regressor",
  "preprocessing": {
    "numeric": "standardize",
    "categorical": "one_hot",
    "missing": "impute"
  },
  "params": {
    "hidden_layer_sizes": [64, 32],
    "activation": "relu",
    "alpha": 0.001,
    "learning_rate_init": 0.001,
    "max_iter": 300,
    "early_stopping": true,
    "random_seed": 42
  },
  "metrics": ["mae", "rmse", "r2"]
}
```

## When to stop tuning

Stop tuning when:

- validation/test performance does not improve meaningfully;
- the tuned model becomes much less interpretable without business-value gain;
- runtime or complexity is disproportionate;
- model results are unstable across splits;
- data quality, label quality, or leakage risk dominates model choice.
