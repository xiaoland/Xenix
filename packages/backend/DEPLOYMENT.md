# Xenix Backend - Aliyun FC Deployment Guide

> **DEPRECATED**: This deployment guide is for the old architecture. ML workers have been extracted to `packages/ml-backend`. See `packages/ml-backend/DEPLOYMENT.md` for current ML worker deployment.

This guide covers deploying the Xenix backend to Aliyun Function Compute (FC) with OSS storage and Python ML workers.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Browser)                                         │
│  - Upload files directly to OSS via presigned URLs          │
│  - Download results via presigned URLs                      │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  xenix-backend (FC HTTP Function)                           │
│  - Node.js/Hono API server                                  │
│  - Generates presigned URLs for frontend                    │
│  - Invokes Python workers asynchronously                    │
│  - Accesses OSS via mounted filesystem (/mnt/oss)           │
└─────────────────────────────────────────────────────────────┘
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
    ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
    │ auto-tune     │  │ manual-tune   │  │ predict       │
    │ worker (FC)   │  │ worker (FC)   │  │ worker (FC)   │
    │ - Python 3.10 │  │ - Python 3.10 │  │ - Python 3.10 │
    │ - ML libs     │  │ - ML libs     │  │ - ML libs     │
    │ - OSS mount   │  │ - OSS mount   │  │ - OSS mount   │
    └───────────────┘  └───────────────┘  └───────────────┘
                               │
                               ▼
                ┌──────────────────────────┐
                │  Aliyun OSS Bucket       │
                │  (via NAS mount)         │
                │  /mnt/oss                │
                │  - datasets/             │
                │  - predictions/          │
                └──────────────────────────┘
```

## Prerequisites

### 1. Install Serverless Devs CLI

```bash
npm install -g @serverless-devs/s
```

### 2. Configure Aliyun Credentials

```bash
s config add
```

Follow the prompts to add your Aliyun AccessKeyID and AccessKeySecret.

### 3. Set Up Aliyun Resources

#### a) Create OSS Bucket

```bash
# In Aliyun Console:
# 1. Go to OSS service
# 2. Create bucket (e.g., xenix-data)
# 3. Choose region (e.g., cn-hangzhou)
# 4. Enable versioning (optional but recommended)
```

#### b) Create NAS File System and Mount OSS

```bash
# In Aliyun Console:
# 1. Go to NAS service
# 2. Create NAS file system in same region as OSS
# 3. Mount OSS bucket to NAS:
#    - Go to File System > Mount Points
#    - Add OSS bucket as data source
#    - Note the NAS server address (format: {fs-id}.{region}.nas.aliyuncs.com)
```

#### c) Create RDS PostgreSQL Database

```bash
# In Aliyun Console:
# 1. Go to RDS service
# 2. Create PostgreSQL instance
# 3. Create database: xenix
# 4. Note connection string
```

#### d) Create Redis Instance (Optional)

```bash
# Only needed if using BullMQ for task queuing
# In Aliyun Console:
# 1. Go to Redis service
# 2. Create instance
# 3. Note connection string
```

## Deployment Steps

### Step 1: Configure Environment Variables

```bash
# Copy example file
cp .env.fc.example .env.fc

# Edit .env.fc with your values
nano .env.fc
```

Fill in:
- `OSS_REGION`, `OSS_ACCESS_KEY_ID`, `OSS_ACCESS_KEY_SECRET`, `OSS_BUCKET`
- `OSS_NAS_SERVER_ADDR` (from NAS mount setup)
- `DATABASE_URL` (PostgreSQL connection string)
- `JWT_SECRET` (generate a secure random string)

### Step 2: Load Environment Variables

```bash
# Export to current shell
export $(cat .env.fc | xargs)
```

### Step 3: Build and Deploy

#### Option A: Deploy Everything (First Time)

```bash
# Build Python layer, copy ML scripts, package backend, and deploy all
pnpm run deploy:all
```

This runs:
1. `build:layer` - Creates Python layer with ML dependencies
2. `build:workers` - Copies ML scripts to each worker directory
3. `package:fc` - Builds and packages backend code
4. Deploys layer, workers, and backend to FC

#### Option B: Deploy Components Separately

```bash
# 1. Build and deploy Python layer (do this first)
pnpm run build:layer
pnpm run deploy:layer

# 2. Copy ML scripts and deploy workers
pnpm run build:workers
pnpm run deploy:workers

# 3. Package and deploy backend
pnpm run deploy:backend
```

### Step 4: Run Database Migrations

```bash
# Connect to RDS and run migrations
DATABASE_URL="your-rds-url" pnpm run db:migrate
```

### Step 5: Test Deployment

```bash
# Get function URL from deployment output
# Test health endpoint
curl https://<your-function-url>/health

# Test presigned URL generation
curl -X POST https://<your-function-url>/datasets/upload-url \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"key": "test/file.xlsx"}'
```

## Deployment Scripts Reference

| Script | Description |
|--------|-------------|
| `build:layer` | Builds Python layer with ML dependencies |
| `build:workers` | Copies ML scripts to worker directories |
| `package:fc` | Builds and packages backend for FC |
| `deploy:layer` | Deploys Python layer to FC |
| `deploy:workers` | Deploys all three Python worker functions |
| `deploy:backend` | Deploys backend HTTP function |
| `deploy:all` | Builds and deploys everything |

## Environment Variables

### Required for Deployment (s.yaml)

These must be exported before running deployment commands:

- `OSS_REGION` - OSS region (e.g., cn-hangzhou)
- `OSS_ACCESS_KEY_ID` - Aliyun Access Key ID
- `OSS_ACCESS_KEY_SECRET` - Aliyun Access Key Secret
- `OSS_BUCKET` - OSS bucket name
- `OSS_ENDPOINT` - OSS endpoint (e.g., oss-cn-hangzhou.aliyuncs.com)
- `OSS_NAS_SERVER_ADDR` - NAS server address for OSS mount
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET` - JWT signing secret
- `REDIS_URL` - Redis connection string (optional)

### Function Runtime Variables

These are set in s.yaml and configured in FC:

- `STORAGE_TYPE=oss` - Use OSS storage (vs local)
- `OSS_MOUNT_POINT=/mnt/oss` - NAS mount path
- `PYTHON_PATH=/usr/bin/python3` - Python executable path
- `ML_TIMEOUT=300000` - ML task timeout (5 minutes)

## Storage Key Patterns

The system uses the following key patterns in OSS:

- **Datasets**: `datasets/{datasetId}/{filename}`
- **Predictions**: `predictions/{taskId}/output.xlsx`
- **Temporary**: `tmp/{uuid}/{filename}`

## Function Configuration

### xenix-backend (Main HTTP Function)

- **Runtime**: custom.debian10 (Node.js)
- **Memory**: 2048 MB
- **Timeout**: 60 seconds
- **Trigger**: HTTP (anonymous)
- **NAS Mount**: /mnt/oss (OSS bucket)
- **Layer**: xenix-python-layer

### Python Workers (auto-tune, manual-tune, predict)

- **Runtime**: python3.10
- **Memory**: 4096 MB
- **Timeout**: 600 seconds (10 minutes)
- **Trigger**: None (async invocation only)
- **NAS Mount**: /mnt/oss (OSS bucket)
- **Layer**: xenix-python-layer

## Troubleshooting

### Issue: "Layer not found"

**Solution**: Deploy the Python layer first:
```bash
pnpm run build:layer
pnpm run deploy:layer
```

### Issue: "OSS mount failed"

**Solution**: Verify NAS configuration:
1. Check `OSS_NAS_SERVER_ADDR` is correct
2. Ensure NAS and OSS bucket are in same region
3. Verify NAS mount configuration in Aliyun console

### Issue: "Python import errors in workers"

**Solution**: Rebuild and redeploy Python layer:
```bash
pnpm run build:layer
pnpm run deploy:layer
# Then redeploy workers
pnpm run deploy:workers
```

### Issue: "Worker timeout"

**Solution**: Increase timeout in s.yaml:
```yaml
timeout: 900  # 15 minutes for large datasets
```

### Issue: "Cannot invoke function"

**Solution**: Check FC client initialization:
1. Verify OSS credentials are correct
2. Check `STORAGE_TYPE=oss` in environment
3. Review backend logs for FC client errors

## Viewing Logs

```bash
# Backend logs
s logs -f xenix-backend --tail

# Worker logs
s logs -f auto-tune-worker --tail
s logs -f manual-tune-worker --tail
s logs -f predict-worker --tail
```

## Updating Deployment

### Update Backend Code Only

```bash
pnpm run deploy:backend
```

### Update Python Workers Only

```bash
pnpm run build:workers
pnpm run deploy:workers
```

### Update Python Dependencies

```bash
# Edit requirements.txt first
pnpm run build:layer
pnpm run deploy:layer
# Redeploy all functions to use new layer
pnpm run deploy:all
```

## Cost Optimization

1. **Use appropriate memory sizes**: Backend needs less memory than workers
2. **Set reasonable timeouts**: Avoid paying for unused execution time
3. **Monitor invocations**: Use FC console to track function calls
4. **OSS lifecycle rules**: Archive old datasets to reduce storage costs
5. **Layer reuse**: Share Python layer across all functions

## Security Best Practices

1. **Never commit credentials**: Keep `.env.fc` in `.gitignore`
2. **Use RAM roles**: Configure FC to use RAM roles instead of AK/SK when possible
3. **Rotate secrets**: Regularly update JWT_SECRET and database passwords
4. **OSS bucket policies**: Restrict public access, use presigned URLs
5. **VPC configuration**: Deploy FC functions in VPC with RDS/Redis

## CI/CD Integration

For automated deployments, add to your CI/CD pipeline:

```bash
# Example GitHub Actions workflow
- name: Deploy to Aliyun FC
  env:
    OSS_REGION: ${{ secrets.OSS_REGION }}
    OSS_ACCESS_KEY_ID: ${{ secrets.OSS_ACCESS_KEY_ID }}
    OSS_ACCESS_KEY_SECRET: ${{ secrets.OSS_ACCESS_KEY_SECRET }}
    # ... other secrets
  run: |
    npm install -g @serverless-devs/s
    s config add --AccessKeyID $OSS_ACCESS_KEY_ID --AccessKeySecret $OSS_ACCESS_KEY_SECRET
    pnpm run deploy:all
```

## Rollback

If deployment fails or issues arise:

```bash
# Rollback to previous version
s version publish --version-id <previous-version-id>

# Or redeploy from last known good commit
git checkout <commit-hash>
pnpm run deploy:all
```

## Support

For issues or questions:
- Check [Aliyun FC documentation](https://help.aliyun.com/document_detail/52895.html)
- Review function logs in FC console
- Open issue in project repository
