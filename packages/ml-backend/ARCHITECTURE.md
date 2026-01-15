# ML Backend Architecture

Pure Python ML backend for Xenix. Input/output through stdio and file system only.

## Overview

Standalone ML operations package. No TypeScript, no HTTP, no external dependencies beyond Python ML libraries.

```
Input (stdin/FC event)
  ↓
Entry point (main.py or fc_handler.py)
  ↓
Operation router
  ├─ batch-train → GridSearchCV auto-tuning
  ├─ single-train → Train with specific params
  └─ predict → Make predictions
  ↓
File system I/O (configurable base path)
  ↓
Output (stdout JSON lines / FC response)
```

## Structure

```
ml_backend/
├── config.py           # Configuration (base path, env vars)
├── types.py            # Pydantic models for I/O validation
├── operations/         # Core ML operations
│   ├── batch_train.py  # GridSearchCV with hyperparameter tuning
│   ├── single_train.py # Training with fixed parameters
│   └── predict.py      # Batch predictions
├── models/             # Model registry
│   └── registry.py     # 12 regression models + param grids
└── utils/
    ├── logger.py       # Structured logging to stdout
    └── file_io.py      # File system operations
```

## Entry Points

### main.py - stdio/shell

Reads JSON from stdin, executes operation, outputs JSON lines to stdout.

**Input**: Single JSON object via stdin
```json
{
  "operation": "batch-train",
  "data": {
    "task_id": 123,
    "input_file": "data.xlsx",
    "model": "regression.ridge",
    ...
  }
}
```

**Output**: JSON lines to stdout
```json
{"type": "log", "severity_text": "INFO", "body": "Starting batch training...", ...}
{"type": "log", "severity_text": "INFO", "body": "Model metrics: R²=0.92", ...}
{"type": "result", "data": {"task_id": 123, "best_params": {...}, ...}}
```

### fc_handler.py - Aliyun FC

Event handler following Aliyun FC Python conventions.

**Signature**: `handler(event, context) -> dict`

**Input**: FC event (dict or bytes)
```python
{
  "operation": "batch-train",
  "data": {...}
}
```

**Output**: FC response
```python
{
  "statusCode": 200,
  "headers": {"Content-Type": "application/json"},
  "body": "{\"success\": true, \"data\": {...}}"
}
```

## Operations

### Batch Training

GridSearchCV hyperparameter optimization.

**Input**:
- `input_file` - Training data path (xlsx/csv)
- `model` - Model name (e.g., `regression.ridge`)
- `feature_columns` - Feature column names
- `target_column` - Target column name
- `param_grid` - Parameter grid for tuning

**Output**:
- `best_params` - Best parameters found
- `metrics` - r2, mse, mae, rmse, cv_scores
- `model_path` - Saved model file path

**Process**:
1. Read training data from file system
2. Split into train/test (80/20)
3. Run GridSearchCV with 5-fold CV
4. Evaluate on test set
5. Save model to file system
6. Return metrics and model path

### Single Training

Training with specific parameters (no tuning).

**Input**: Same as batch training but `params` instead of `param_grid`

**Output**: Same as batch training (without cv_scores)

**Process**: Same as batch training but skips GridSearchCV

### Prediction

Batch predictions using trained model.

**Input**:
- `train_data` - Training data path
- `predict_data` - Prediction data path or inline JSON array
- `output_path` - Where to save predictions
- `model` - Model name
- `params` - Model parameters
- `feature_columns` - Feature columns
- `target_column` - Target column

**Output**:
- `predictions_path` - Saved predictions file path
- `record_count` - Number of predictions
- `metrics` - Optional (if target exists in predict data)

**Process**:
1. Read training data
2. Train model with specified params
3. Read prediction data (file or inline)
4. Generate predictions
5. Save predictions to file system
6. Calculate metrics if target available

## Model Registry

12 regression models with default parameter grids:

**Linear Models**:
- `regression.linear` - Linear Regression
- `regression.ridge` - Ridge Regression
- `regression.lasso` - Lasso Regression
- `regression.bayesian_ridge` - Bayesian Ridge

**Polynomial**:
- `regression.polynomial` - Polynomial Regression (pipeline)

**Instance-based**:
- `regression.knn` - K-Nearest Neighbors

**Tree-based**:
- `regression.decision_tree` - Decision Tree
- `regression.random_forest` - Random Forest

**Boosting**:
- `regression.adaboost` - AdaBoost
- `regression.gbdt` - Gradient Boosting (GBDT)
- `regression.xgboost` - XGBoost
- `regression.lightgbm` - LightGBM

Each model has:
- Model class (sklearn/xgboost/lightgbm)
- Default parameters
- Parameter grid for GridSearchCV

## File System I/O

All file operations use configurable base path.

**Path Resolution**:
- Absolute paths used as-is
- Relative paths resolved from `ML_BASE_PATH`

**Supported Formats**:
- Input: `.xlsx`, `.xls`, `.csv`
- Output: `.xlsx`, `.csv` (default: csv)

**Directories**:
- `ML_BASE_PATH` - Base directory (default: `/tmp/ml-backend`)
- `MODEL_STORAGE_PATH` - Model storage (default: `{BASE_PATH}/models`)
- `DATA_STORAGE_PATH` - Data storage (default: `{BASE_PATH}/data`)

All directories created automatically on startup.

## Logging

Structured logging to stdout using OpenTelemetry-like format.

**Log Entry**:
```json
{
  "type": "log",
  "timestamp": 1234567890123456789,
  "observed_timestamp": 1234567890123456789,
  "severity_text": "INFO",
  "severity_number": 9,
  "body": "Log message",
  "resource": {
    "service.name": "ml-backend",
    "service.version": "2.0.0"
  },
  "attributes": {
    "task_id": 123,
    ...
  }
}
```

**Severity Levels**:
- DEBUG (5)
- INFO (9)
- WARNING (13)
- ERROR (17)
- CRITICAL (21)

Logs written to stdout, one JSON object per line. External systems can parse and store logs as needed.

## Configuration

Environment variables:

**Required**: None (all have defaults)

**Optional**:
- `ML_BASE_PATH` - Base path for file operations
- `MODEL_STORAGE_PATH` - Model storage directory
- `DATA_STORAGE_PATH` - Data storage directory
- `DATABASE_URL` - PostgreSQL connection (for future DB logging)
- `LOG_LEVEL` - Logging level (DEBUG/INFO/WARNING/ERROR)

## Error Handling

**Validation Errors**: Pydantic validates all inputs. Invalid data raises validation error with details.

**File Errors**: Missing files, unsupported formats raise specific errors.

**Model Errors**: Unknown models, invalid parameters raise descriptive errors.

**Training Errors**: Failures during training (e.g., convergence issues) propagated with full traceback.

**Error Output**:
```json
{
  "type": "error",
  "error": "Error message",
  "traceback": "Full traceback..."
}
```

Exit code 1 for shell, statusCode 500 for FC.

## Performance

**Parallel Training**: GridSearchCV uses `n_jobs=-1` (all cores)

**Memory**: Models and data loaded into memory. Large datasets may require more RAM.

**File I/O**: Single-threaded file operations. Fast for typical dataset sizes (<100MB).

**Optimization**:
- Use CSV instead of Excel for faster I/O
- Reduce parameter grid size for faster tuning
- Use single-train for production (skip tuning)

## Deployment

**Local/Shell**: Run `main.py` directly with Python 3.8+

**Aliyun FC**: Deploy `fc_handler.py` as Python 3.9/3.10 function

See [DEPLOYMENT.md](DEPLOYMENT.md) for deployment instructions.
