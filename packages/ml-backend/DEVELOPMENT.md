# ML Backend Development

## Setup

### Prerequisites

- Python 3.8+
- pip

### Install

```bash
pip install -r requirements.txt
```

## Development

### Run Locally

```bash
# Test batch training
echo '{
  "operation": "batch-train",
  "data": {
    "task_id": 123,
    "input_file": "test_data/train.csv",
    "model": "regression.ridge",
    "feature_columns": ["x1", "x2"],
    "target_column": "y",
    "param_grid": {"alpha": [0.1, 1.0, 10.0]}
  }
}' | python main.py

# Test single training
echo '{
  "operation": "single-train",
  "data": {
    "task_id": 124,
    "input_file": "test_data/train.csv",
    "model": "regression.xgboost",
    "feature_columns": ["x1", "x2"],
    "target_column": "y",
    "params": {"n_estimators": 100, "max_depth": 5}
  }
}' | python main.py

# Test prediction
echo '{
  "operation": "predict",
  "data": {
    "task_id": 125,
    "train_data": "test_data/train.csv",
    "predict_data": "test_data/predict.csv",
    "output_path": "output/predictions.csv",
    "model": "regression.ridge",
    "params": {"alpha": 1.0},
    "feature_columns": ["x1", "x2"],
    "target_column": "y"
  }
}' | python main.py
```

### Environment Variables

```bash
export ML_BASE_PATH=/tmp/ml-backend
export MODEL_STORAGE_PATH=/tmp/ml-backend/models
export DATA_STORAGE_PATH=/tmp/ml-backend/data
export LOG_LEVEL=DEBUG
```

### Test Data

Create test data:

```python
# create_test_data.py
import pandas as pd
import numpy as np

# Training data
np.random.seed(42)
X = np.random.randn(100, 2)
y = 2 * X[:, 0] + 3 * X[:, 1] + np.random.randn(100) * 0.1

df_train = pd.DataFrame({
    'x1': X[:, 0],
    'x2': X[:, 1],
    'y': y
})
df_train.to_csv('test_data/train.csv', index=False)

# Prediction data
X_pred = np.random.randn(20, 2)
df_pred = pd.DataFrame({
    'x1': X_pred[:, 0],
    'x2': X_pred[:, 1]
})
df_pred.to_csv('test_data/predict.csv', index=False)
```

## Structure

```
ml-backend/
├── main.py              # stdio entry point
├── fc_handler.py        # Aliyun FC entry point
├── ml_backend/          # Core package
│   ├── __init__.py
│   ├── config.py        # Configuration
│   ├── types.py         # Pydantic models
│   ├── operations/      # ML operations
│   │   ├── __init__.py
│   │   ├── batch_train.py
│   │   ├── single_train.py
│   │   └── predict.py
│   ├── models/          # Model registry
│   │   ├── __init__.py
│   │   └── registry.py
│   └── utils/           # Utilities
│       ├── __init__.py
│       ├── logger.py
│       └── file_io.py
├── requirements.txt     # Dependencies
└── tests/               # Unit tests
```

## Available Models

Test all 12 regression models:

```bash
# Linear models
regression.linear
regression.ridge
regression.lasso
regression.bayesian_ridge

# Polynomial
regression.polynomial

# Instance-based
regression.knn

# Tree-based
regression.decision_tree
regression.random_forest

# Boosting
regression.adaboost
regression.gbdt
regression.xgboost
regression.lightgbm
```

## Debugging

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
echo '...' | python main.py
```

Output includes:
- Log entries with timestamps
- Model parameters
- Training metrics
- File paths
- Error tracebacks

## Testing

Run tests (when available):

```bash
python -m pytest tests/
```

## Code Style

Follow PEP 8. Use type hints.

```python
def batch_train(input_data: BatchTrainInput) -> BatchTrainOutput:
    ...
```

## Performance

Optimize for large datasets:

- Use CSV instead of Excel
- Reduce param_grid size
- Use single-train for production
- Enable parallel training (n_jobs=-1)

Monitor memory usage:

```bash
# Linux
/usr/bin/time -v python main.py < input.json

# macOS
/usr/bin/time -l python main.py < input.json
```
