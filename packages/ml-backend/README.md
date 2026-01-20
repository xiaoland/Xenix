# Xenix ML Backend

Pure Python ML backend for Xenix. Performs machine learning operations (training, prediction) through stdio and file system.

## Operations

- **batch-train** - Auto-tuning with GridSearchCV
- **single-train** - Training with specific parameters
- **predict** - Predictions with trained models

## Models

**12 regression models**:

- Linear Regression, Ridge, Lasso
- Polynomial Regression
- Bayesian Ridge Regression
- K-Nearest Neighbors
- Decision Tree, Random Forest
- AdaBoost, GBDT, XGBoost, LightGBM

**2 classification models**:

- Logistic Regression
- Random Forest Classifier

## Installation

Using PDM (recommended, pyproject.toml is the single source of truth):

```bash
pdm install
```

If you need a pip-compatible file, export from PDM first:

```bash
pdm export -f requirements --without-hashes -o /tmp/ml-backend-deps.txt
pip install -r /tmp/ml-backend-deps.txt
```

## Usage

### Shell/stdio (Local)

```bash
# Batch training
echo '{
  "operation": "batch-train",
  "data": {
    "task_id": 123,
    "input_file": "data/training.xlsx",
    "model": "regression.ridge",
    "feature_columns": ["age", "income"],
    "target_column": "score",
    "param_grid": {"alpha": [0.1, 1.0, 10.0]}
  }
}' | python main.py

# Single training
echo '{
  "operation": "single-train",
  "data": {
    "task_id": 124,
    "input_file": "data/training.csv",
    "model": "regression.xgboost",
    "feature_columns": ["x1", "x2"],
    "target_column": "y",
    "params": {"n_estimators": 100, "max_depth": 5}
  }
}' | python main.py

# Prediction
echo '{
  "operation": "predict",
  "data": {
    "task_id": 125,
    "train_data": "data/train.csv",
    "predict_data": "data/predict.csv",
    "output_path": "output/predictions.csv",
    "model": "regression.ridge",
    "params": {"alpha": 1.0},
    "feature_columns": ["age", "income"],
    "target_column": "score"
  }
}' | python main.py
```

### Aliyun FC

Deploy `fc_handler.py` as Aliyun Function Compute handler.

See [DEPLOYMENT.md](DEPLOYMENT.md) for deployment instructions.

## Input/Output

**Input**: JSON via stdin (for main.py) or FC event (for fc_handler.py)

**Output**: JSON lines to stdout

- Logs: `{"type": "log", "severity_text": "INFO", "body": "message", ...}`
- Result: `{"type": "result", "data": {...}}`
- Error: `{"type": "error", "error": "message", "traceback": "..."}`

## Configuration

Environment variables:

- `ML_BASE_PATH` - Base path for file operations (default: `/tmp/ml-backend`)
- `MODEL_STORAGE_PATH` - Model storage path (default: `{BASE_PATH}/models`)
- `DATA_STORAGE_PATH` - Data storage path (default: `{BASE_PATH}/data`)
- `DATABASE_URL` - PostgreSQL connection (optional, for logging)
- `LOG_LEVEL` - Logging level (default: `INFO`)

## Architecture

Service-oriented design with controllers and model services:

```
ml-backend/
├── main.py              # stdio entry point
├── fc_handler.py        # Aliyun FC entry point
├── ml_backend/          # Core package
│   ├── config.py        # Configuration
│   ├── types.py         # Type definitions (Pydantic)
│   ├── controllers/     # Operation controllers
│   │   ├── batch_train.py
│   │   ├── single_train.py
│   │   └── predict.py
│   ├── services/        # Model services (service-oriented)
│   │   ├── regression/  # Regression models
│   │   │   ├── base.py  # Abstract base class
│   │   │   ├── ridge.py, lasso.py, linear.py
│   │   │   └── ...      # 12 models total
│   │   └── classification/  # Classification models
│   │       ├── base.py
│   │       └── ...      # 2 models total
│   └── utils/           # Utilities
│       ├── logger.py
│       └── file_io.py
└── tests/               # Tests
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture.

## License

MIT
