# Aliyun FC Deployment Checklist

Use this checklist to ensure a successful deployment to Aliyun Function Compute.

## Pre-Build

- [ ] Update @xenix/shared if needed (`cd ../shared && pnpm run build`)
- [ ] Run `pnpm test` - all tests pass
- [ ] Update version in [package.json](package.json) if needed
- [ ] Review environment variables in [.env.fc.example](.env.fc.example)
- [ ] Ensure all code changes are committed to git

## Build

- [ ] Run `pnpm run build:fc` successfully
- [ ] Verify [dist-fc/index.js](dist-fc/index.js) exists
- [ ] Verify [dist-fc/ml/](dist-fc/ml/) contains all Python scripts
- [ ] Check bundle size (should be < 50MB uncompressed)
  ```bash
  # Check bundle size
  ls -lh dist-fc/index.js
  # or on Windows
  dir dist-fc\index.js
  ```

## Package

- [ ] Run `pnpm run package:fc`
- [ ] Verify [fc-deploy.zip](fc-deploy.zip) created
- [ ] Check zip size (should be < 50MB)

## Aliyun FC Configuration

### Function Settings
- [ ] Function created with **Node.js 22** runtime
- [ ] Memory: **2048MB** minimum (for ML tasks)
- [ ] Timeout: **600 seconds** (10 minutes for long ML operations)
- [ ] HTTP trigger configured
- [ ] Upload [fc-deploy.zip](fc-deploy.zip) as code package

### Environment Variables
Configure all variables from [.env.fc.example](.env.fc.example):
- [ ] `NODE_ENV=production`
- [ ] `BACKEND_PORT=9000`
- [ ] `FRONTEND_URL` (your frontend domain)
- [ ] `DATABASE_URL` (Aliyun RDS PostgreSQL connection string)
- [ ] `REDIS_URL` (Aliyun Redis connection string)
- [ ] `JWT_SECRET` (secure 32+ character secret)
- [ ] `UPLOAD_DIR=/tmp/uploads`
- [ ] `PYTHON_PATH=/usr/bin/python3`
- [ ] `ML_TIMEOUT=300000`

Note: `FC_FUNC_CODE_PATH` and `FC_FUNCTION_VERSION` are automatically set by FC.

## Python Layer Setup

Choose one option:

### Option A: Custom Layer (Recommended)
- [ ] Create layer with Python packages from [requirements.txt](requirements.txt)
- [ ] Layer structure: `python/lib/python3.10/site-packages/`
- [ ] Upload layer to Aliyun FC
- [ ] Attach layer to function
- [ ] Set `PYTHONPATH` environment variable if needed

### Option B: Bootstrap Installation
- [ ] Create bootstrap script that installs packages to /tmp on cold start
- [ ] Set as function initialization script
- [ ] Test cold start installation time

## Database & Services

- [ ] Aliyun RDS PostgreSQL instance created
- [ ] Database schema exists
- [ ] Database migrations applied (run `pnpm run db:migrate` with DATABASE_URL pointing to RDS)
- [ ] Aliyun Redis instance created
- [ ] VPC networking configured (if RDS/Redis in VPC)
- [ ] Security groups allow FC to access RDS (port 5432)
- [ ] Security groups allow FC to access Redis (port 6379)
- [ ] Test database connection from FC function

## Post-Deployment Verification

### 1. Health Check
```bash
curl https://your-fc-domain.com/health
```
Expected response:
```json
{
  "status": "ok",
  "timestamp": "2024-01-14T...",
  "environment": "production",
  "version": "..."
}
```

### 2. Authentication
```bash
curl -X POST https://your-fc-domain.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'
```
Expected: JWT token response

### 3. Database Connection
- [ ] Check FC logs for successful database connection
- [ ] Verify no connection timeout errors

### 4. Redis Connection
- [ ] Check FC logs for successful Redis connection
- [ ] Submit test ML task to verify queue works

### 5. Python Environment
- [ ] Submit ML tune task via API
- [ ] Verify Python script executes successfully
- [ ] Check FC logs for Python script output

### 6. File Upload
- [ ] Upload test dataset via `/data` endpoint
- [ ] Verify file saved to `/tmp/uploads`
- [ ] Check file permissions and accessibility

## Monitoring

- [ ] Set up Aliyun CloudMonitor alerts for:
  - Function errors
  - Function timeouts
  - High memory usage
  - Cold start duration
- [ ] Configure log collection to Aliyun Log Service
- [ ] Set up error notifications (email/SMS)
- [ ] Monitor Python script execution times
- [ ] Monitor database connection pool usage

## Performance Optimization

- [ ] Monitor cold start frequency and duration
- [ ] Consider provisioned instances if cold starts are frequent
- [ ] Monitor bundle size and optimize if needed
- [ ] Set up function warming if necessary

## BullMQ Worker Considerations

The current backend includes a BullMQ worker for ML tasks. For production:

### Option A: Separate Worker Function
- [ ] Create separate FC function for worker
- [ ] Use Timer trigger to invoke periodically (every 1-5 minutes)
- [ ] Deploy same code but run worker instead of HTTP server

### Option B: Use FC Async Invoke
- [ ] Replace BullMQ with FC async invocation
- [ ] Modify ML task submission to use FC async API
- [ ] No separate Redis queue needed

### Option C: Keep Worker in HTTP Function (Not Recommended)
- [ ] Worker runs alongside HTTP server
- [ ] May cause cold start issues
- [ ] Not ideal for scaling

## Rollback Plan

If deployment fails:
- [ ] Keep previous function version available
- [ ] Document current version number before deployment
- [ ] Know how to switch traffic back to previous version
- [ ] Have database backup ready
- [ ] Test rollback procedure in non-production environment

## Success Criteria

Deployment is successful when:
- ✅ Health endpoint returns 200 OK
- ✅ All API endpoints respond correctly
- ✅ Database queries execute successfully
- ✅ Redis connection works (BullMQ jobs enqueue)
- ✅ Python ML scripts execute without errors
- ✅ File uploads work to /tmp
- ✅ No errors in FC logs
- ✅ Function completes within timeout limits
- ✅ Memory usage stays within allocated limits (< 2048MB)

## Troubleshooting

Common issues and solutions:

### Python ImportError
- Verify Python layer is attached
- Check PYTHONPATH environment variable
- Ensure requirements.txt packages match layer packages

### File Upload Fails
- Verify UPLOAD_DIR is set to `/tmp/uploads`
- Check FC function has write permission to /tmp
- Consider using Aliyun OSS for persistent storage

### Database Connection Timeout
- Verify VPC configuration
- Check security group rules
- Increase DATABASE_URL connection timeout parameter

### BullMQ Jobs Not Processing
- Verify Redis connection
- Check if worker needs separate FC function
- Consider using Aliyun MNS for job queue
