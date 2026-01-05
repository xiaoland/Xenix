# ML Business Logic Directory

Python-based machine learning logic for model training, tuning, and prediction.

## Overview

This directory contains:

- TypeScript orchestration code (`index.ts`)
- Python scripts for ML operations
- Model implementations organized by ML type

## Directory Structure

```text
ml/
├── index.ts              # Node.js orchestration
├── base.py               # Base Python classes
├── structured_io.py      # JSON I/O for Node-Python communication
├── auto_tune_model.py    # GridSearchCV auto-tuning
├── manual_tune_model.py  # Manual parameter tuning
├── predict.py            # Batch prediction
├── scan_models.py        # Scan available models
└── regression/           # Regression model implementations
    ├── base.py
    ├── linear_regression_hyperparameter_tuning.py
    ├── ridge.py
    ├── lasso.py
    ├── polynomial_regression.py
    ├── k_nearest_neighbors.py
    ├── regression_decision_tree.py
    ├── random_forest.py
    ├── adaboost.py
    ├── gbdt.py
    ├── xgboost.py
    ├── lightgbm.py
    └── bayesian_ridge_regression.py
```

## Python-Node Communication

### structured_io.py

Handles JSON-based communication between Node.js and Python:

```python
from structured_io import read_input, write_output, write_log

# Read input from Node.js
params = read_input()

# Write logs during execution
write_log("info", "Training started")

# Write final output
write_output({"success": True, "metrics": {...}})
```

### Execution Flow

1. Node.js calls `pythonExecutor.ts` with script path and JSON input
2. Python script reads input via `structured_io.read_input()`
3. Python executes ML logic, writing logs via `write_log()`
4. Python writes result via `write_output()`
5. Node.js parses JSON output and updates database

## Model Implementation

### Base Class Pattern

Each model type has a base class in `{type}/base.py`:

```python
class RegressionModel:
    name: str           # Model identifier
    display_name: str   # Human-readable name
    param_schema: dict  # JSON Schema for parameters

    def get_model(self, params: dict):
        """Return sklearn model instance"""
        pass

    def get_default_param_grid(self) -> dict:
        """Return default GridSearchCV param grid"""
        pass
```

### Model Registration

Models are discovered by `scan_models.py`:

```python
# Each model file exports:
MODEL_CLASS = LinearRegressionModel  # The model class
```

### param_schema Format

JSON Schema defining tunable parameters:

```python
param_schema = {
    "type": "object",
    "properties": {
        "n_estimators": {
            "type": "integer",
            "default": 100,
            "minimum": 1,
            "maximum": 1000,
            "description": "Number of trees"
        },
        "max_depth": {
            "type": "integer",
            "default": 10,
            "minimum": 1,
            "maximum": 50
        }
    }
}
```

## Script Reference

### auto_tune_model.py

GridSearchCV-based hyperparameter tuning.

Input:

```json
{
  "datasetPath": "path/to/dataset.xlsx",
  "featureColumns": ["col1", "col2"],
  "targetColumn": "target",
  "model": "sklearn.ensemble.RandomForestRegressor"
}
```

Output:

```json
{
  "success": true,
  "params": {"n_estimators": 100, "max_depth": 10},
  "metrics": {"mse": 0.05, "mae": 0.15, "r2": 0.92}
}
```

### manual_tune_model.py

Train with user-specified parameters.

Input:

```json
{
  "datasetPath": "path/to/dataset.xlsx",
  "featureColumns": ["col1", "col2"],
  "targetColumn": "target",
  "model": "sklearn.ensemble.RandomForestRegressor",
  "params": {"n_estimators": 200, "max_depth": 15}
}
```

### predict.py

Batch prediction using trained model.

Input:

```json
{
  "predictionFilePath": "path/to/predict.xlsx",
  "trainingDatasetPath": "path/to/train.xlsx",
  "featureColumns": ["col1", "col2"],
  "targetColumn": "target",
  "model": "sklearn.ensemble.RandomForestRegressor",
  "params": {"n_estimators": 100}
}
```

Output:

```json
{
  "success": true,
  "outputFile": "path/to/predictions.xlsx"
}
```

### scan_models.py

Scan and return available models with their schemas.

Output:

```json
{
  "success": true,
  "models": [
    {
      "name": "sklearn.linear_model.LinearRegression",
      "displayName": "Linear Regression",
      "paramSchema": {...}
    }
  ]
}
```

## Supported Models

### Regression

| Model | File | Key Parameters |
|-------|------|----------------|
| Linear Regression | linear_regression_hyperparameter_tuning.py | fit_intercept |
| Ridge | ridge.py | alpha |
| Lasso | lasso.py | alpha |
| Polynomial | polynomial_regression.py | degree |
| KNN | k_nearest_neighbors.py | n_neighbors, weights |
| Decision Tree | regression_decision_tree.py | max_depth, min_samples_split |
| Random Forest | random_forest.py | n_estimators, max_depth |
| AdaBoost | adaboost.py | n_estimators, learning_rate |
| GBDT | gbdt.py | n_estimators, learning_rate, max_depth |
| XGBoost | xgboost.py | n_estimators, learning_rate, max_depth |
| LightGBM | lightgbm.py | n_estimators, learning_rate, num_leaves |
| Bayesian Ridge | bayesian_ridge_regression.py | alpha_1, alpha_2, lambda_1, lambda_2 |

## Adding a New Model

1. Create file in appropriate type folder (e.g., `regression/new_model.py`)
2. Implement model class extending base class
3. Define `param_schema` with JSON Schema
4. Export `MODEL_CLASS`
5. Run `/api/models/sync` to register model
