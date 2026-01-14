# Xenix Backend Deployment Guide for Aliyun Function Compute

This guide provides detailed instructions for deploying the Xenix backend to Aliyun Function Compute (FC) HTTP Server Mode.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [One-Time Setup](#one-time-setup)
4. [Build Process](#build-process)
5. [Python Layer Creation](#python-layer-creation)
6. [FC Function Configuration](#fc-function-configuration)
7. [Deployment](#deployment)
8. [Post-Deployment Verification](#post-deployment-verification)
9. [BullMQ Worker Setup](#bullmq-worker-setup)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Node.js 22+ and pnpm installed locally
- Aliyun account with Function Compute service enabled
- Aliyun CLI (`aliyun-cli`) or `fcli` installed (optional, for CLI deployment)
- Access to Aliyun RDS PostgreSQL and Redis instances

---

## Architecture Overview

### Deployment Package Structure

```
fc-deploy.zip
├── index.js              # Bundled Node.js application (all dependencies)
├── package.json          # Minimal package.json
├── requirements.txt      # Python dependencies
└── ml/                   # Python ML scripts
    ├── auto_tune_model.py
    ├── manual_tune_model.py
    ├── predict.py
    ├── predict_on_file.py
    ├── predict_on_json.py
    ├── base.py
    ├── structured_io.py
    ├── predict_helpers.py
    ├── scan_models.py
    └── regression/
        ├── __init__.py
        ├── base.py
        └── [12 regression model files].py
```

### Key Design Decisions

1. **Single Bundle**: All Node.js dependencies bundled into `index.js` (FC requirement)
2. **Python Scripts**: Included as separate `.py` files in `ml/` directory
3. **File Storage**: Uses `/tmp/uploads` for temporary file storage in FC
4. **Managed Services**: Connects to external Aliyun RDS (PostgreSQL) and Redis
5. **Python Packages**: Installed via FC Layer or bootstrap script

---

## One-Time Setup

### 1. Create Aliyun Services

#### RDS PostgreSQL Instance
```bash
# Create RDS instance via Aliyun Console or CLI
# Note the connection string:
# postgresql://username:password@your-rds.aliyuncs.com:5432/xenix
```

#### Redis Instance
```bash
# Create Redis instance via Aliyun Console or CLI
# Note the connection string:
# redis://r-xxxxx.redis.rds.aliyuncs.com:6379
```

### 2. Run Database Migrations

```bash
cd packages/backend

# Set DATABASE_URL to your RDS instance
export DATABASE_URL="postgresql://user:pass@your-rds.aliyuncs.com:5432/xenix"

# Run migrations
pnpm run db:migrate
```

### 3. Configure Environment Variables

Copy [.env.fc.example](.env.fc.example) and update with your values:

```bash
cp .env.fc.example .env.fc
# Edit .env.fc with your actual values
```

---

## Build Process

### Quick Start

```bash
# From packages/backend directory

# 1. Build for FC (builds shared, bundles dependencies, copies Python scripts)
pnpm run build:fc

# 2. Create deployment package
pnpm run package:fc
```

### Detailed Build Steps

#### Step 1: Build @xenix/shared Package

The backend depends on the shared workspace package, which must be built first:

```bash
cd ../shared
pnpm run build
cd ../backend
```

Or use the built-in script:
```bash
pnpm run build:shared
```

#### Step 2: Bundle with tsup

The FC-specific tsup configuration ([tsup.config.fc.ts](tsup.config.fc.ts)) bundles all dependencies:

```bash
tsup --config tsup.config.fc.ts
```

This creates:
- `dist-fc/index.js` - Single bundled file with all Node.js code

Key configuration:
- `noExternal: [/.*/]` - Bundles ALL dependencies
- `external: [...]` - Excludes Node.js built-ins
- Injects `__dirname` and `__filename` for Python path resolution

#### Step 3: Copy Python Scripts

```bash
pnpm run copy:assets
```

This copies all `.py` files from `src/business/ml/` to `dist-fc/ml/`, preserving directory structure.

#### Step 4: Create Deployment Package

```bash
pnpm run package:fc
```

This creates `fc-deploy.zip` containing:
- Bundled `index.js`
- Minimal `package.json`
- Python scripts in `ml/` directory
- `requirements.txt` for Python dependencies

---

## Python Layer Creation

FC requires Python packages to be pre-installed. Two options:

### Option A: Custom Layer (Recommended)

#### Create Layer Package

```bash
# Create layer directory structure
mkdir -p layer/python/lib/python3.10/site-packages

# Install Python packages
pip3 install -r requirements.txt -t layer/python/lib/python3.10/site-packages

# Create layer zip
cd layer
zip -r python-layer.zip python/
```

#### Upload to Aliyun FC

Via Console:
1. Navigate to **Function Compute** > **Layers**
2. Click **Create Layer**
3. Upload `python-layer.zip`
4. Select **Python 3.10** runtime
5. Note the Layer ARN

Via CLI:
```bash
fcli layer publish \
  --layer-name xenix-python-deps \
  --code-zip-file python-layer.zip \
  --compatible-runtime python3.10
```

### Option B: Bootstrap Installation (Alternative)

Create a bootstrap script that installs packages on cold start:

**bootstrap.sh:**
```bash
#!/bin/bash
set -e

if [ ! -d "/tmp/python-packages" ]; then
    echo "Installing Python dependencies..."
    pip3 install -r requirements.txt -t /tmp/python-packages --no-cache-dir
fi

export PYTHONPATH="/tmp/python-packages:$PYTHONPATH"
exec node index.js
```

Upload bootstrap script and set as function initialization handler.

**Note**: This increases cold start time significantly (~30-60 seconds).

---

## FC Function Configuration

### Create Function

Via Aliyun Console:

1. Navigate to **Function Compute** > **Services** > Create Service
2. Service Name: `xenix`
3. Create Function within service:
   - Function Name: `xenix-backend`
   - Runtime: **Node.js 22**
   - Memory: **2048 MB** (minimum for ML tasks)
   - Timeout: **600 seconds** (10 minutes)
   - Handler: Leave default (we use HTTP trigger)

### Configure HTTP Trigger

1. Click **Create Trigger**
2. Trigger Type: **HTTP Trigger**
3. Auth Type: Choose based on your security requirements
4. Methods: **GET, POST, PUT, DELETE**
5. Note the trigger URL

### Attach Python Layer

1. In function configuration, scroll to **Layers**
2. Click **Add Layer**
3. Select the Python layer created earlier
4. Save changes

### Set Environment Variables

In Function Configuration > Environment Variables, add all variables from [.env.fc.example](.env.fc.example):

```bash
NODE_ENV=production
BACKEND_PORT=9000
FRONTEND_URL=https://your-frontend-domain.com
DATABASE_URL=postgresql://user:pass@your-rds.aliyuncs.com:5432/xenix
REDIS_URL=redis://r-xxxxx.redis.rds.aliyuncs.com:6379
JWT_SECRET=your-secure-secret-at-least-32-characters-long
UPLOAD_DIR=/tmp/uploads
PYTHON_PATH=/usr/bin/python3
ML_TIMEOUT=300000
```

### VPC Configuration (if RDS/Redis in VPC)

1. Navigate to **Network Configuration**
2. Enable VPC
3. Select VPC, vSwitch, and Security Group
4. Ensure Security Group allows:
   - Outbound to RDS (port 5432)
   - Outbound to Redis (port 6379)

---

## Deployment

### Via Aliyun Console

1. Navigate to your function
2. Click **Code** tab
3. Click **Upload** > **Upload .zip file**
4. Select `fc-deploy.zip`
5. Click **Deploy**
6. Wait for deployment to complete

### Via Aliyun CLI

```bash
# Configure Aliyun CLI first
aliyun configure

# Deploy function
fcli function update \
  --service-name xenix \
  --function-name xenix-backend \
  --code-zip-file fc-deploy.zip \
  --region cn-hangzhou
```

### Via fcli (Function Compute CLI)

```bash
# Install fcli
npm install -g @alicloud/fcli

# Configure credentials
fcli config

# Deploy
fcli function update \
  -s xenix \
  -f xenix-backend \
  -r cn-hangzhou \
  --code-zip-file fc-deploy.zip
```

---

## Post-Deployment Verification

### 1. Health Check

```bash
curl https://<function-url>/health
```

Expected response:
```json
{
  "status": "ok",
  "timestamp": "2024-01-14T12:00:00.000Z",
  "environment": "production",
  "version": "1"
}
```

### 2. Authentication Test

```bash
# Create test user first, then:
curl -X POST https://<function-url>/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'
```

### 3. Check Logs

Via Console:
1. Navigate to function
2. Click **Logs** tab
3. Check for errors or warnings

Via CLI:
```bash
fcli logs tail -s xenix -f xenix-backend
```

Look for:
- ✅ "Starting server" message
- ✅ Database connection success
- ✅ Redis connection success
- ❌ No error stack traces

### 4. Test ML Functionality

Submit a test ML task:

```bash
TOKEN="<your-jwt-token>"

curl -X POST https://<function-url>/tune \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "inputFile": "/path/to/dataset.csv",
    "model": "regression.linear_regression_hyperparameter_tuning",
    "featureColumns": ["feature1", "feature2"],
    "targetColumn": "target"
  }'
```

Check logs for Python script execution.

---

## BullMQ Worker Setup

The backend uses BullMQ for async ML task processing. In FC, you have options:

### Option A: Separate Worker Function (Recommended)

Create a second FC function dedicated to processing jobs:

#### 1. Create Worker Function

Same code package, but different entry point:

**worker.js:**
```javascript
import './dist-fc/index.js';
// Import and start worker only
import { startWorker } from './jobs/mlTaskWorker.js';
startWorker();
```

#### 2. Configure Worker Function

- Runtime: Node.js 22
- Memory: 2048 MB
- Timeout: 900 seconds (15 minutes for long tasks)
- Trigger: **Timer Trigger** (every 1-5 minutes)

#### 3. Deploy Worker

Upload same `fc-deploy.zip` but configure to run worker code.

### Option B: Use FC Async Invoke

Replace BullMQ with FC async invocation:

1. Modify ML task submission to use FC async API
2. Remove Redis dependency
3. Use FC's built-in async processing

**Pros**: No separate Redis needed
**Cons**: Less control over job retry/failure handling

### Option C: Combined Function (Not Recommended)

Run worker alongside HTTP server in same function.

**Cons**:
- Cold start issues
- Worker may not process jobs during idle periods
- Resource contention

---

## Troubleshooting

### Issue: Python ImportError

**Symptoms**: ML tasks fail with `ModuleNotFoundError`

**Solutions**:
1. Verify Python layer is attached to function
2. Check `PYTHONPATH` environment variable
3. Ensure layer packages match [requirements.txt](requirements.txt)
4. Test Python imports:
   ```bash
   # SSH into FC environment (if available) or use debug endpoint
   python3 -c "import pandas; print(pandas.__version__)"
   ```

### Issue: File Upload Fails

**Symptoms**: `/data` endpoint returns 500 error

**Solutions**:
1. Verify `UPLOAD_DIR=/tmp/uploads` in environment variables
2. Check FC logs for permission errors
3. Ensure upload directory is created (code in [src/index.ts](src/index.ts:24-27) handles this)
4. Consider migrating to Aliyun OSS for persistent storage

### Issue: Database Connection Timeout

**Symptoms**: Queries timeout, connection pool errors

**Solutions**:
1. Verify VPC configuration:
   - Function is in same VPC as RDS
   - Security group allows port 5432
2. Check RDS whitelist includes FC VPC CIDR
3. Test connection:
   ```bash
   # From function logs
   psql $DATABASE_URL -c "SELECT 1"
   ```
4. Increase connection timeout in `DATABASE_URL`:
   ```
   postgresql://user:pass@host:5432/db?connect_timeout=10
   ```

### Issue: Cold Starts Are Slow

**Symptoms**: First request takes 5-10 seconds

**Solutions**:
1. Reduce bundle size:
   - Analyze with `esbuild-visualizer`
   - Remove unused dependencies
2. Use FC Provisioned Instances:
   - Pre-warm function instances
   - Configure in FC console
3. Optimize initialization:
   - Lazy load heavy modules
   - Pre-connect to database/Redis

### Issue: Memory Limit Exceeded

**Symptoms**: Function crashes with OOM error

**Solutions**:
1. Increase function memory (Console > Configuration)
2. Optimize Python scripts:
   - Process data in chunks
   - Use `del` to free memory
3. Monitor memory usage in logs

### Issue: BullMQ Jobs Not Processing

**Symptoms**: Tasks stuck in queue

**Solutions**:
1. Verify Redis connection:
   ```bash
   redis-cli -u $REDIS_URL ping
   ```
2. Check worker function is running (if separate)
3. Review worker logs for errors
4. Test job submission:
   ```javascript
   import { queue } from './queues/index.js';
   await queue.add('test', { data: 'test' });
   ```

### Issue: CORS Errors

**Symptoms**: Frontend requests blocked

**Solutions**:
1. Verify `FRONTEND_URL` matches your frontend domain exactly
2. Check CORS middleware in [src/index.ts](src/index.ts:27-33)
3. Ensure credentials are enabled:
   ```typescript
   cors({
     origin: config.FRONTEND_URL,
     credentials: true,
   })
   ```

---

## Monitoring Best Practices

### Set Up CloudMonitor Alerts

1. Navigate to **CloudMonitor** > **Application Monitoring**
2. Configure alerts for:
   - Function error rate > 5%
   - Function timeout > 10%
   - Memory usage > 80%
   - Cold start duration > 5s

### Enable Log Service

1. Function Configuration > Log Configuration
2. Enable Aliyun Log Service
3. Create log project and logstore
4. Query logs using SQL-like syntax

### Custom Metrics

Add custom metrics to your code:

```typescript
import logger from './utils/logger';

logger.info({
  metric: 'ml_task_duration',
  duration: taskDuration,
  model: modelName
}, 'ML task completed');
```

Query metrics in Log Service:
```sql
* | SELECT model, AVG(duration) as avg_duration
  WHERE metric = 'ml_task_duration'
  GROUP BY model
```

---

## Next Steps

- [ ] Set up CI/CD pipeline for automated deployments
- [ ] Migrate file storage from `/tmp` to Aliyun OSS
- [ ] Implement function warming to reduce cold starts
- [ ] Create separate worker function for BullMQ processing
- [ ] Set up performance monitoring and alerts
- [ ] Document rollback procedures
- [ ] Create staging environment for testing

---

## Additional Resources

- [Aliyun Function Compute Documentation](https://www.alibabacloud.com/help/fc)
- [Node.js Runtime Reference](https://www.alibabacloud.com/help/fc/user-guide/nodejs-runtime)
- [HTTP Trigger Configuration](https://www.alibabacloud.com/help/fc/user-guide/http-triggers)
- [FC Layer Documentation](https://www.alibabacloud.com/help/fc/user-guide/layers)
- [FC CLI (fcli) Documentation](https://github.com/aliyun/fcli)

---

For issues or questions, please refer to [FC_DEPLOYMENT_CHECKLIST.md](FC_DEPLOYMENT_CHECKLIST.md) or consult the Aliyun FC support team.
