# ML Backend Deployment

Deploy ml-backend to Aliyun Function Compute using Serverless Devs.

## Prerequisites

**Required**:

- Aliyun account with Function Compute access
- Aliyun NAS with OSS mount configured
- [Serverless Devs](https://www.serverless-devs.com/) installed

**Install Serverless Devs**:

```bash
npm install -g @serverless-devs/s
```

**Configure Aliyun access**:

```bash
s config add
# Follow prompts to add Aliyun AccessKey
```

## Build Python Layer

Build dependencies layer for FC:

```bash
./build_layer.sh
```

This creates a `python/` directory with all dependencies (pandas, scikit-learn, xgboost, lightgbm, etc.).

## Deploy

### 1. Deploy Python Dependencies Layer

```bash
s deploy xenix-ml-python-layer
```

This creates a layer with all Python dependencies that will be shared across all functions.

### 2. Deploy ML Functions

Deploy all three functions (batch-train, single-train, predict):

```bash
s deploy
```

Or deploy individual functions:

```bash
s deploy ml-batch-train
s deploy ml-single-train
s deploy ml-predict
```

## Configuration

### Environment Variables

Set these in `.env` file or as environment variables:

```bash
# Required
OSS_NAS_SERVER_ADDR=your-nas-server.cn-hangzhou.nas.aliyuncs.com
DATABASE_URL=postgresql://user:pass@host/xenix

# Optional (defaults shown)
ML_BASE_PATH=/mnt/oss/ml-backend
MODEL_STORAGE_PATH=/mnt/oss/ml-backend/models
DATA_STORAGE_PATH=/mnt/oss/ml-backend/data
LOG_LEVEL=INFO
```

### Function Configuration

All three functions use the same settings (configured in `s.yaml`):

- **Runtime**: Python 3.10
- **Handler**: `fc_handler.handler`
- **Memory**: 4096MB
- **Timeout**: 600 seconds (10 minutes)
- **Code**: Current directory (./)
- **NAS Mount**: `/mnt/oss` (mapped to OSS bucket)

## Test Functions

Test batch training:

```bash
s invoke ml-batch-train --event '{
  "operation": "batch-train",
  "data": {
    "task_id": 123,
    "input_file": "/mnt/oss/data/train.csv",
    "model": "regression.ridge",
    "feature_columns": ["x1", "x2"],
    "target_column": "y",
    "param_grid": {"alpha": [0.1, 1.0, 10.0]}
  }
}'
```

Test single training:

```bash
s invoke ml-single-train --event '{
  "operation": "single-train",
  "data": {
    "task_id": 124,
    "input_file": "/mnt/oss/data/train.csv",
    "model": "regression.xgboost",
    "feature_columns": ["x1", "x2"],
    "target_column": "y",
    "params": {"n_estimators": 100, "max_depth": 5}
  }
}'
```

Test prediction:

```bash
s invoke ml-predict --event '{
  "operation": "predict",
  "data": {
    "task_id": 125,
    "train_data": "/mnt/oss/data/train.csv",
    "predict_data": "/mnt/oss/data/predict.csv",
    "output_path": "/mnt/oss/output/predictions.csv",
    "model": "regression.ridge",
    "params": {"alpha": 1.0},
    "feature_columns": ["x1", "x2"],
    "target_column": "y"
  }
}'
```

## Monitoring

View function logs:

```bash
s logs ml-batch-train
s logs ml-single-train
s logs ml-predict
```

View metrics:

```bash
s metrics ml-batch-train
```

## Update Deployment

After code changes, rebuild and redeploy:

```bash
# Re-export dependencies from pyproject.toml and rebuild the layer
./build_layer.sh
s deploy xenix-ml-python-layer

# Deploy updated functions
s deploy
```

## Remove Deployment

Remove all functions and layer:

```bash
s remove
```

## Architecture

Three separate FC functions all use the same code (`fc_handler.py`) but can be invoked independently:

```
┌─────────────────────┐
│  ml-batch-train     │──┐
│  (FC Function)      │  │
└─────────────────────┘  │
                         │
┌─────────────────────┐  │    ┌──────────────────┐
│  ml-single-train    │──┼───→│  fc_handler.py   │
│  (FC Function)      │  │    │  (shared code)   │
└─────────────────────┘  │    └──────────────────┘
                         │
┌─────────────────────┐  │
│  ml-predict         │──┘
│  (FC Function)      │
└─────────────────────┘

All functions share:
- Python dependencies layer (xenix-ml-python-deps)
- NAS mount (/mnt/oss)
- Same codebase (ml_backend/)
```

## File Storage

Training data, models, and predictions are stored in NAS/OSS:

```
/mnt/oss/ml-backend/
├── models/           # Trained models (.pkl files)
├── data/             # Training data
└── output/           # Predictions
```

## Troubleshooting

**Layer build fails**:

```bash
# Use Python 3.10 environment
python3.10 -m venv venv
source venv/bin/activate
./build_layer.sh
```

**Function timeout**:

- Increase timeout in `s.yaml` (max 600 seconds)
- Check data file size (large files need more time)
- Monitor memory usage in FC console

**NAS mount error**:

- Verify `OSS_NAS_SERVER_ADDR` is correct
- Check NAS permissions (userId/groupId must match)
- Ensure NAS and FC function in same VPC

**Import errors**:

- Verify layer deployed successfully: `s info xenix-ml-python-layer`
- Check `PYTHONPATH` includes `/opt/python` and `/code`
- Rebuild layer after dependency changes in pyproject.toml

## Resources

- [Serverless Devs Documentation](https://docs.serverless-devs.com/)
- [Aliyun FC Documentation](https://help.aliyun.com/product/50980.html)
- [FC Python Runtime](https://help.aliyun.com/zh/functioncompute/fc/user-guide/event-handlers-1-1)
