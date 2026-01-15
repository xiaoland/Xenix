# ML Backend Deployment

## Aliyun FC Deployment

Deploy ml-backend as Aliyun Function Compute handler.

### Prepare

Install dependencies:

```bash
pip install -r requirements.txt -t ./package
cp -r ml_backend ./package/
cp fc_handler.py ./package/
cd package && zip -r ../ml-backend-fc.zip . && cd ..
```

### Deploy with Aliyun CLI

```bash
# Create function
aliyun fc create-function \
  --service-name xenix \
  --function-name ml-backend \
  --runtime python3.10 \
  --handler fc_handler.handler \
  --memory-size 1024 \
  --timeout 300 \
  --code-zip-file ml-backend-fc.zip

# Update function
aliyun fc update-function \
  --service-name xenix \
  --function-name ml-backend \
  --code-zip-file ml-backend-fc.zip
```

### FC Configuration

**Runtime**: Python 3.10 (or 3.9)

**Memory**: 1024MB minimum (recommended: 2048MB for large datasets)

**Timeout**: 300 seconds (5 minutes)

**Handler**: `fc_handler.handler`

**Environment Variables**:
```bash
ML_BASE_PATH=/tmp/ml-backend
MODEL_STORAGE_PATH=/tmp/ml-backend/models
DATA_STORAGE_PATH=/tmp/ml-backend/data
LOG_LEVEL=INFO
```

### NAS/OSS Mount (Optional)

Mount OSS for persistent model storage:

```bash
# Mount OSS bucket to /mnt/oss
ML_BASE_PATH=/mnt/oss/ml-backend
MODEL_STORAGE_PATH=/mnt/oss/ml-backend/models
DATA_STORAGE_PATH=/mnt/oss/ml-backend/data
```

### Test Invocation

```bash
aliyun fc invoke-function \
  --service-name xenix \
  --function-name ml-backend \
  --event '{
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

## Docker Deployment

Self-hosted deployment with Docker.

### Dockerfile

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY ml_backend ./ml_backend
COPY main.py .

# Set environment
ENV ML_BASE_PATH=/data
ENV MODEL_STORAGE_PATH=/data/models
ENV DATA_STORAGE_PATH=/data/datasets

# Create directories
RUN mkdir -p /data/models /data/datasets

CMD ["python", "main.py"]
```

### Build and Run

```bash
# Build image
docker build -t xenix-ml-backend:2.0.0 .

# Run container
docker run -i \
  -v $(pwd)/data:/data \
  -e LOG_LEVEL=INFO \
  xenix-ml-backend:2.0.0 < input.json
```

## Environment Variables

**ML_BASE_PATH** - Base path for file operations
Default: `/tmp/ml-backend`

**MODEL_STORAGE_PATH** - Model storage directory
Default: `{BASE_PATH}/models`

**DATA_STORAGE_PATH** - Data storage directory
Default: `{BASE_PATH}/data`

**LOG_LEVEL** - Logging level
Default: `INFO`
Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`

**DATABASE_URL** - PostgreSQL connection (optional)
Format: `postgresql://user:pass@host/db`

## Monitoring

### Aliyun FC Logs

View function logs:

```bash
# Recent logs
aliyun fc get-function-logs \
  --service-name xenix \
  --function-name ml-backend \
  --lines 100

# Follow logs
aliyun fc get-function-logs \
  --service-name xenix \
  --function-name ml-backend \
  --follow
```

### Performance Metrics

Monitor:
- Execution time
- Memory usage
- Error rates
- Model training metrics (R², RMSE)

Logs include structured JSON with metrics.

## Troubleshooting

### Timeout Errors

Increase timeout or reduce dataset size:

```bash
aliyun fc update-function \
  --service-name xenix \
  --function-name ml-backend \
  --timeout 600
```

### Out of Memory

Increase memory allocation:

```bash
aliyun fc update-function \
  --service-name xenix \
  --function-name ml-backend \
  --memory-size 2048
```

### Module Not Found

Ensure all dependencies in requirements.txt are installed in package.

### File Not Found

Check ML_BASE_PATH and file paths. Use absolute paths or ensure relative paths resolve correctly.

## Rollback

Revert to previous version:

```bash
# List versions
aliyun fc list-function-versions \
  --service-name xenix \
  --function-name ml-backend

# Publish version
aliyun fc publish-function-version \
  --service-name xenix \
  --function-name ml-backend

# Create alias to specific version
aliyun fc create-alias \
  --service-name xenix \
  --function-name ml-backend \
  --alias-name production \
  --version-id 2
```
