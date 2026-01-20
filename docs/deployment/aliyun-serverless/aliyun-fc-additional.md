# Additional Guide of Aliyun FC Deployment

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
