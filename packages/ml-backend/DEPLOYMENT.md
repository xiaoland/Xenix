# ML Backend Deployment Guide

## Building for Production

### Build Steps

```bash
# Build TypeScript
pnpm -F @xenix/ml-backend build

# Output: dist/

# Build with Aliyun FC configuration
pnpm build:fc

# Package for deployment
pnpm package:fc
```

## Deployment Options

### Option 1: Aliyun FC (Recommended)

Deploy as Aliyun Function Compute worker:

```bash
# 1. Build with FC config
pnpm build:fc

# 2. Package for FC
pnpm package:fc

# 3. Deploy
pnpm deploy:ml-backend
```

**FC Configuration:**

- Runtime: Node.js 18
- Memory: 1024MB (recommended, minimum 512MB)
- Timeout: 300 seconds (5 minutes)
- Trigger: Event-based invocation from backend

**Features:**

- Automatic scaling
- Pay-per-execution pricing
- Direct OSS access via NAS mount
- Python 3.10 available in FC environment

### Option 2: Self-Hosted (Docker)

Run as standalone service:

```dockerfile
# Dockerfile
FROM node:18-alpine

# Install Python and ML dependencies
RUN apk add --no-cache python3 pip
RUN pip install scikit-learn xgboost lightgbm pandas numpy

WORKDIR /app

COPY dist/ ./dist/
COPY ml/ ./ml/
COPY node_modules ./node_modules/

CMD ["node", "dist/index.js"]
```

Build and run:

```bash
# Build image
docker build -t xenix-ml-backend:1.0.0 .

# Run container
docker run -e PYTHON_PATH=/usr/bin/python3 \
  -e OSS_ENDPOINT=... \
  -e ML_TIMEOUT=300000 \
  xenix-ml-backend:1.0.0
```

## Environment Configuration

### Aliyun FC Environment Variables

```bash
# Python
PYTHON_PATH=/usr/bin/python3
ML_TIMEOUT=300000

# Execution mode
ML_ADAPTER_TYPE=aliyun-fc

# Aliyun services
ALIYUN_FC_FUNCTION_NAME=xenix-ml-backend
ALIYUN_FC_SERVICE_NAME=xenix

# Aliyun OSS
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
OSS_BUCKET=xenix-prod-data
OSS_ACCESS_KEY_ID=your-access-key
OSS_ACCESS_KEY_SECRET=your-secret-key

# Database (for logging)
DATABASE_URL=postgres://user:pass@rds-host/xenix

# Logging
LOG_LEVEL=info
```

### Self-Hosted Environment Variables

```bash
# Python
PYTHON_PATH=/usr/bin/python3
ML_TIMEOUT=300000

# Execution mode
ML_ADAPTER_TYPE=spawn

# File storage
STORAGE_TYPE=oss
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
OSS_BUCKET=xenix-data
OSS_ACCESS_KEY_ID=your-access-key
OSS_ACCESS_KEY_SECRET=your-secret-key

# Database
DATABASE_URL=postgres://user:pass@host/xenix
```

## Python Environment

### Requirements

The ML backend requires Python 3.8+ with these packages:

```bash
# ml/requirements.txt
scikit-learn>=1.0.0
xgboost>=1.5.0
lightgbm>=3.2.0
pandas>=1.3.0
numpy>=1.20.0
joblib>=1.0.0
```

### Installation

```bash
# Install dependencies
pip install -r ml/requirements.txt

# Verify installation
python3 -c "import sklearn, xgboost, lightgbm; print('OK')"
```

## Aliyun OSS Setup

### Bucket Configuration

```bash
# Create bucket
aliyun oss mb oss://xenix-prod-models

# Create directories
aliyun oss mkdir oss://xenix-prod-models/models/
aliyun oss mkdir oss://xenix-prod-models/logs/
aliyun oss mkdir oss://xenix-prod-models/cache/

# Set lifecycle rules (auto-delete old files)
```

### NAS Mount (FC Only)

ML Backend in FC accesses OSS via NAS mount at `/mnt/oss`:

```typescript
// In FC environment, OSS files are accessible at /mnt/oss
const modelPath = '/mnt/oss/models/my-model.pkl'
const dataPath = '/mnt/oss/datasets/data.csv'
```

## Monitoring & Logging

### Aliyun FC Logs

```bash
# View function logs
aliyun fc logs --function-name xenix-ml-backend --max-items 100

# Stream logs in real-time
aliyun fc logs --function-name xenix-ml-backend --follow

# Export to Aliyun SLS (Simple Log Service)
# Configure in FC console
```

### Application Logging

Logs are written to:

- Console (stdout/stderr)
- Database (`task_logs` table)
- Aliyun SLS

### Performance Monitoring

Monitor:

- Execution time
- Memory usage
- Error rates
- Python process metrics

```typescript
// Example: Log training metrics
logger.log('Training completed', 'INFO', {
  executionTime: endTime - startTime,
  memoryUsed: process.memoryUsage().heapUsed,
  modelsGenerated: 5,
  bestScore: 0.92
})
```

## Database Integration

### Task Logging

Training operations create records in database:

```sql
-- Create task
INSERT INTO tasks (id, type, status, input, output)
VALUES ('task-123', 'auto-tune', 'running', {...}, NULL)

-- Update during execution
UPDATE tasks SET output = {...} WHERE id = 'task-123'

-- Mark complete
UPDATE tasks SET status = 'completed', completed_at = NOW() WHERE id = 'task-123'
```

### Async Invocation

From backend, invoke ML Backend asynchronously:

```typescript
const adapter = new AliyunFCAdapter()

// Returns 202 Accepted immediately
const result = await adapter.batchTrain({
  taskId: 'task-123',
  inputFile: 's3://bucket/data.csv',
  model: 'linear_regression',
  paramGrid: { /* ... */ }
})

// Frontend polls /tasks/:id for completion
// Database updated by ml-backend directly
```

## Deployment Checklist

- [ ] Update version in package.json
- [ ] Run tests: `pnpm -F @xenix/ml-backend test`
- [ ] Check types: `pnpm -F @xenix/ml-backend type-check`
- [ ] Verify Python scripts work locally
- [ ] Test with sample data
- [ ] Build: `pnpm -F @xenix/ml-backend build`
- [ ] Build for FC: `pnpm build:fc`
- [ ] Package: `pnpm package:fc`
- [ ] Deploy: `pnpm deploy:ml-backend`
- [ ] Monitor logs for errors
- [ ] Test with backend

## Rollback

### If Issues Occur

```bash
# Option 1: Revert FC function
aliyun fc update-function \
  --service-name xenix \
  --function-name ml-backend \
  --code <previous-version.zip>

# Option 2: Revert code to previous tag
git checkout v1.0.0
pnpm -F @xenix/ml-backend build:fc
pnpm package:fc
pnpm deploy:ml-backend
```

## Troubleshooting

### Function Timeout

Increase timeout in FC console or environment:

```bash
# Increase timeout to 10 minutes
ML_TIMEOUT=600000
```

For very large datasets, consider:

- Dataset sampling
- Parallel processing
- Running on larger FC memory tier

### Out of Memory

```bash
# Increase FC memory tier
aliyun fc update-function \
  --service-name xenix \
  --function-name ml-backend \
  --memory-size 3072  # 3GB
```

### Python Module Not Found

```bash
# Verify requirements.txt installed
pip install -r ml/requirements.txt

# Check Python path
echo $PYTHON_PATH

# Verify in FC environment
aliyun fc invoke --function-name ml-backend --payload '...'
```

### Database Connection Error

```bash
# Verify DATABASE_URL
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1"

# Check security group rules in Aliyun console
```

## Performance Optimization

### Model Caching

Cache trained models for reuse:

```typescript
const modelCache = new Map<string, Model>()

function getOrLoadModel(path: string) {
  if (!modelCache.has(path)) {
    modelCache.set(path, loadModel(path))
  }
  return modelCache.get(path)
}
```

### Data Streaming

For large datasets, stream data instead of loading into memory:

```typescript
const stream = fs.createReadStream('data.csv')
const data = await loadStreamingData(stream)
```

### Parallel Processing

Parallelize GridSearchCV:

```python
# auto_tune_model.py
from sklearn.model_selection import GridSearchCV

clf = GridSearchCV(
    model,
    param_grid,
    n_jobs=-1,  # Use all cores
    cv=5
)
```

## Resources

- [Root DEPLOYMENT.md](../../DEPLOYMENT.md)
- [ML Backend Development](./DEVELOPMENT.md)
- [ML Backend Architecture](./ARCHITECTURE.md)
- [Aliyun FC Documentation](https://www.alibabacloud.com/help/en/fc/)
- [scikit-learn Documentation](https://scikit-learn.org/)
