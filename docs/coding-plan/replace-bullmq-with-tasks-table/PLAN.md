# Refactor Plan: Replace BullMQ with Tasks Table and ML Backend Adapters

## Overview

Replace BullMQ and Redis with a simpler tasks table-based system that uses adapters to invoke ml-backend either via Aliyun FC or process spawn.

**Branch:** `claude/replace-bullmq-tasks-table-bxLPe`
**Base:** `feat/deploy-to-aliyun-fc`

## Context

The ml-backend has been refactored into a pure Python script that can:
- Run as a standalone CLI (via stdio)
- Run as an Aliyun Function Compute handler

Currently, the backend:
- Has BullMQ/Redis dependencies defined but barely used
- Uses direct invocation pattern (not queuing)
- Uses adapter pattern (SpawnAdapter for local, AliyunFCAdapter for production)
- Tasks are tracked in PostgreSQL `tasks` table

## Goals

1. **Remove BullMQ and Redis** - eliminate over-engineering, use PostgreSQL exclusively
2. **Create ml_backend_workers table** - track available ML backend execution environments
3. **Add task-to-worker association** - each task references which worker executes it
4. **Update ml-backend CLI** - support `--base-path` argument for Aliyun FC compatibility
5. **Refactor adapter selection** - use database configuration instead of environment detection

## New Database Schema

### ml_backend_workers table

```sql
CREATE TABLE ml_backend_workers (
  id              SERIAL PRIMARY KEY,
  name            TEXT NOT NULL UNIQUE,              -- e.g., "local-dev", "aliyun-fc-prod"
  created_by      UUID REFERENCES users(id),          -- User who created this worker
  adapter         TEXT NOT NULL                       -- 'aliyun-fc' | 'spawn'
    CHECK (adapter IN ('aliyun-fc', 'spawn')),
  adapter_params  JSONB NOT NULL DEFAULT '{}',        -- Adapter-specific configuration
  is_default      BOOLEAN NOT NULL DEFAULT false,     -- Default worker for new tasks
  is_active       BOOLEAN NOT NULL DEFAULT true,      -- Whether this worker is enabled
  created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ml_backend_workers_adapter ON ml_backend_workers(adapter);
CREATE INDEX idx_ml_backend_workers_default ON ml_backend_workers(is_default) WHERE is_default = true;
```

**adapter_params examples:**

For `spawn` adapter:
```json
{
  "pythonPath": "python3",
  "mlBackendPath": "/path/to/ml-backend",
  "basePath": "/tmp/ml-backend"
}
```

For `aliyun-fc` adapter:
```json
{
  "serviceName": "xenix",
  "timeout": 60000,
  "basePath": "/mnt/oss"  // Will be combined with /tasks/{task_id} per task
}
```

### Updated tasks table

```sql
-- Add new column
ALTER TABLE tasks ADD COLUMN ml_backend_worker_id INTEGER REFERENCES ml_backend_workers(id);

-- Index for worker-based queries
CREATE INDEX idx_tasks_worker ON tasks(ml_backend_worker_id);
```

**Migration strategy:**
- Existing tasks without `ml_backend_worker_id` will be NULL (historical tasks)
- New tasks MUST specify a worker OR use the default worker

## Implementation Steps

### Phase 1: Database Schema (Migrations)

**File:** `packages/backend/src/database/migrations/002_add_ml_backend_workers.sql`

```sql
-- Create ml_backend_workers table
CREATE TABLE ml_backend_workers (
  id              SERIAL PRIMARY KEY,
  name            TEXT NOT NULL UNIQUE,
  created_by      UUID REFERENCES users(id),
  adapter         TEXT NOT NULL CHECK (adapter IN ('aliyun-fc', 'spawn')),
  adapter_params  JSONB NOT NULL DEFAULT '{}',
  is_default      BOOLEAN NOT NULL DEFAULT false,
  is_active       BOOLEAN NOT NULL DEFAULT true,
  created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ml_backend_workers_adapter ON ml_backend_workers(adapter);
CREATE INDEX idx_ml_backend_workers_default ON ml_backend_workers(is_default) WHERE is_default = true;

-- Add ml_backend_worker_id to tasks
ALTER TABLE tasks ADD COLUMN ml_backend_worker_id INTEGER REFERENCES ml_backend_workers(id);
CREATE INDEX idx_tasks_worker ON tasks(ml_backend_worker_id);

-- Insert default workers
INSERT INTO ml_backend_workers (name, adapter, adapter_params, is_default)
VALUES
  ('local-spawn', 'spawn', '{"basePath": "/tmp/ml-backend"}', true),
  ('aliyun-fc-prod', 'aliyun-fc', '{"serviceName": "xenix", "timeout": 60000, "basePath": "/mnt/oss"}', false);
```

**Files to update:**
- `packages/backend/src/database/schema.ts` - add TypeScript types
- `packages/backend/src/database/migrations/` - create migration file
- `packages/backend/src/repositories/MLBackendWorkerRepository.ts` - NEW: CRUD for workers

### Phase 2: ML Backend CLI Enhancement

**File:** `packages/ml-backend/main.py`

**Current:**
```python
# No CLI arguments, reads from stdin
operation_request = json.loads(sys.stdin.read())
```

**Updated:**
```python
import argparse

parser = argparse.ArgumentParser(description='ML Backend CLI')
parser.add_argument('--base-path', type=str, help='Base path for file operations')
args = parser.parse_args()

# Override Config.BASE_PATH if provided
if args.base_path:
    os.environ['ML_BASE_PATH'] = args.base_path
    Config.reload()  # Force reload configuration

# Then read operation from stdin as before
operation_request = json.loads(sys.stdin.read())
```

**File:** `packages/ml-backend/ml_backend/config.py`

Add reload method:
```python
@classmethod
def reload(cls):
    """Reload configuration from environment variables"""
    cls.BASE_PATH = os.getenv("ML_BASE_PATH", "/tmp/ml-backend")
    cls.MODEL_STORAGE_PATH = os.getenv("MODEL_STORAGE_PATH", f"{cls.BASE_PATH}/models")
    cls.DATA_STORAGE_PATH = os.getenv("DATA_STORAGE_PATH", f"{cls.BASE_PATH}/data")
    cls.ensure_directories()
```

### Phase 3: Adapter Refactoring

**Current architecture:**
```
getMLBackendAdapter() → Auto-detects environment → Returns adapter
```

**New architecture:**
```
getMLBackendAdapter(workerId: number) → Loads worker config from DB → Returns adapter
```

**File:** `packages/backend/src/adapters/ml-backend/index.ts`

**Current:**
```typescript
export async function getMLBackendAdapter(): Promise<MLBackendAdapter> {
  // Auto-detect based on environment
  if (fcInvokeService) return new AliyunFCAdapter(fcInvokeService);
  return new SpawnAdapter();
}
```

**Updated:**
```typescript
export async function getMLBackendAdapter(
  workerId: number
): Promise<MLBackendAdapter> {
  const workerRepo = new MLBackendWorkerRepository();
  const worker = await workerRepo.findById(workerId);

  if (!worker) {
    throw new Error(`ML backend worker ${workerId} not found`);
  }

  if (!worker.is_active) {
    throw new Error(`ML backend worker ${workerId} is inactive`);
  }

  switch (worker.adapter) {
    case 'aliyun-fc':
      return new AliyunFCAdapter(worker.adapter_params);
    case 'spawn':
      return new SpawnAdapter(worker.adapter_params);
    default:
      throw new Error(`Unknown adapter type: ${worker.adapter}`);
  }
}
```

**File:** `packages/backend/src/adapters/ml-backend/spawn-adapter.ts`

**Current:**
```typescript
export class SpawnAdapter implements MLBackendAdapter {
  async executeBatchTrain(params: BatchTrainParams): Promise<void> {
    const mlBackendPath = path.join(__dirname, '../../../ml-backend/main.py');
    // Spawn process...
  }
}
```

**Updated:**
```typescript
export interface SpawnAdapterParams {
  pythonPath?: string;      // Default: 'python3'
  mlBackendPath?: string;   // Default: auto-detect
  basePath?: string;        // Passed as --base-path
}

export class SpawnAdapter implements MLBackendAdapter {
  private pythonPath: string;
  private mlBackendPath: string;
  private basePath?: string;

  constructor(params: SpawnAdapterParams = {}) {
    this.pythonPath = params.pythonPath || 'python3';
    this.mlBackendPath = params.mlBackendPath || this.detectMLBackendPath();
    this.basePath = params.basePath;
  }

  async executeBatchTrain(params: BatchTrainParams): Promise<void> {
    const args = [this.mlBackendPath];

    // Add --base-path if configured
    if (this.basePath) {
      args.push('--base-path', this.basePath);
    }

    const child = spawn(this.pythonPath, args, { stdio: ['pipe', 'pipe', 'pipe'] });
    // ... rest of execution
  }
}
```

**File:** `packages/backend/src/adapters/ml-backend/aliyun-fc-adapter.ts`

**Current:**
```typescript
export class AliyunFCAdapter implements MLBackendAdapter {
  constructor(private fcClient: FCInvokeService) {}

  async executeBatchTrain(params: BatchTrainParams): Promise<void> {
    await this.fcClient.invokeFunction('ml-batch-train-worker', {
      operation: 'batch-train',
      data: params
    });
  }
}
```

**Updated:**
```typescript
export interface AliyunFCAdapterParams {
  serviceName: string;      // e.g., 'xenix'
  timeout?: number;         // Default: 60000
  basePath?: string;        // Base path on FC side (e.g., '/mnt/oss')
}

export class AliyunFCAdapter implements MLBackendAdapter {
  private params: AliyunFCAdapterParams;
  private fcClient: FCInvokeService;

  constructor(params: AliyunFCAdapterParams) {
    this.params = params;
    this.fcClient = FCInvokeService.getInstance(); // Singleton
  }

  async executeBatchTrain(params: BatchTrainParams): Promise<void> {
    const taskBasePath = `${this.params.basePath || '/mnt/oss'}/tasks/${params.taskId}`;

    await this.fcClient.invokeFunction('ml-batch-train-worker', {
      operation: 'batch-train',
      data: params,
      basePath: taskBasePath  // Pass task-specific base path
    });
  }
}
```

### Phase 4: Update API Routes

**File:** `packages/backend/src/routes/train.ts`

**Current:**
```typescript
router.post('/batch-train', async (req, res) => {
  // ... validation ...

  // Create task in DB
  const taskId = await taskRepo.create({ type: 'batch-train', ... });

  // Invoke immediately
  setImmediate(async () => {
    const adapter = await getMLBackendAdapter();
    await adapter.executeBatchTrain({ taskId, ... });
  });

  res.json({ taskId, message: 'Batch training started' });
});
```

**Updated:**
```typescript
router.post('/batch-train', async (req, res) => {
  // ... validation ...

  // Get default worker or use specified worker
  const workerId = req.body.workerId || (await getDefaultWorker()).id;

  // Create task in DB with worker reference
  const taskId = await taskRepo.create({
    type: 'batch-train',
    ml_backend_worker_id: workerId,
    parameter: { ... }
  });

  // Invoke immediately with worker-specific adapter
  setImmediate(async () => {
    const adapter = await getMLBackendAdapter(workerId);
    await adapter.executeBatchTrain({ taskId, ... });
  });

  res.json({ taskId, workerId, message: 'Batch training started' });
});
```

**Helper function:**
```typescript
async function getDefaultWorker(): Promise<MLBackendWorker> {
  const workerRepo = new MLBackendWorkerRepository();
  const defaultWorker = await workerRepo.findDefaultWorker();

  if (!defaultWorker) {
    throw new Error('No default ML backend worker configured');
  }

  return defaultWorker;
}
```

### Phase 5: Remove BullMQ and Redis

**Files to delete:**
- `packages/backend/src/queues/index.ts`
- `packages/backend/src/utils/queueHelper.ts`
- `packages/backend/src/jobs/mlTaskWorker.ts`
- `packages/backend/src/jobs/mlTaskProcessor.ts`

**Files to update:**
- `packages/backend/package.json` - remove `bullmq` and `ioredis`
- `packages/backend/src/config/index.ts` - remove `REDIS_URL`
- `.env.example` - remove Redis configuration

**package.json changes:**
```diff
{
  "dependencies": {
-   "bullmq": "^5.38.1",
-   "ioredis": "^5.4.2",
    // ... other deps
  }
}
```

### Phase 6: New Repository and Types

**File:** `packages/backend/src/repositories/MLBackendWorkerRepository.ts` (NEW)

```typescript
export class MLBackendWorkerRepository {
  async findById(id: number): Promise<MLBackendWorker | null> {
    const result = await pool.query(
      'SELECT * FROM ml_backend_workers WHERE id = $1',
      [id]
    );
    return result.rows[0] || null;
  }

  async findDefaultWorker(): Promise<MLBackendWorker | null> {
    const result = await pool.query(
      'SELECT * FROM ml_backend_workers WHERE is_default = true AND is_active = true LIMIT 1'
    );
    return result.rows[0] || null;
  }

  async findByAdapter(adapter: 'aliyun-fc' | 'spawn'): Promise<MLBackendWorker[]> {
    const result = await pool.query(
      'SELECT * FROM ml_backend_workers WHERE adapter = $1 AND is_active = true',
      [adapter]
    );
    return result.rows;
  }

  async create(data: CreateMLBackendWorkerDTO): Promise<MLBackendWorker> {
    const result = await pool.query(
      `INSERT INTO ml_backend_workers (name, created_by, adapter, adapter_params, is_default)
       VALUES ($1, $2, $3, $4, $5)
       RETURNING *`,
      [data.name, data.created_by, data.adapter, data.adapter_params, data.is_default || false]
    );
    return result.rows[0];
  }

  async update(id: number, data: Partial<UpdateMLBackendWorkerDTO>): Promise<MLBackendWorker> {
    const result = await pool.query(
      `UPDATE ml_backend_workers
       SET name = COALESCE($1, name),
           adapter_params = COALESCE($2, adapter_params),
           is_default = COALESCE($3, is_default),
           is_active = COALESCE($4, is_active),
           updated_at = NOW()
       WHERE id = $5
       RETURNING *`,
      [data.name, data.adapter_params, data.is_default, data.is_active, id]
    );
    return result.rows[0];
  }
}
```

**File:** `packages/backend/src/types/ml-backend.ts`

```typescript
export type MLBackendAdapterType = 'aliyun-fc' | 'spawn';

export interface MLBackendWorker {
  id: number;
  name: string;
  created_by: string | null;  // UUID
  adapter: MLBackendAdapterType;
  adapter_params: Record<string, any>;
  is_default: boolean;
  is_active: boolean;
  created_at: Date;
  updated_at: Date;
}

export interface SpawnAdapterParams {
  pythonPath?: string;
  mlBackendPath?: string;
  basePath?: string;
}

export interface AliyunFCAdapterParams {
  serviceName: string;
  timeout?: number;
  basePath?: string;
}
```

## Testing Strategy

### Local Development Testing

1. **Create spawn worker:**
```bash
curl -X POST http://localhost:3000/api/ml-workers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "local-dev-spawn",
    "adapter": "spawn",
    "adapter_params": {
      "basePath": "/tmp/ml-backend-test"
    },
    "is_default": true
  }'
```

2. **Submit batch-train task:**
```bash
curl -X POST http://localhost:3000/api/train/batch-train \
  -H "Content-Type: application/json" \
  -d '{
    "workItemId": 1,
    "model": "regression.ridge",
    "featureColumns": ["col1", "col2"],
    "targetColumn": "target",
    "paramGrid": {"alpha": [0.1, 1.0, 10.0]}
  }'
```

3. **Verify:**
- Task created with `ml_backend_worker_id`
- ml-backend invoked with `--base-path /tmp/ml-backend-test`
- Results stored in tasks table

### Production Testing (Aliyun FC)

1. **Create FC worker:**
```sql
INSERT INTO ml_backend_workers (name, adapter, adapter_params, is_default)
VALUES (
  'aliyun-fc-prod',
  'aliyun-fc',
  '{"serviceName": "xenix", "basePath": "/mnt/oss"}',
  true
);
```

2. **Submit task to FC:**
- Task should invoke FC function
- FC function receives `basePath: /mnt/oss/tasks/{taskId}`
- ml-backend reads/writes from `/mnt/oss/tasks/{taskId}/`

## Migration Checklist

- [ ] Create `ml_backend_workers` table migration
- [ ] Add `ml_backend_worker_id` column to `tasks` table
- [ ] Insert default workers (spawn for dev, FC for prod)
- [ ] Update ml-backend `main.py` to support `--base-path` CLI arg
- [ ] Add `Config.reload()` method to ml-backend
- [ ] Create `MLBackendWorkerRepository`
- [ ] Refactor `getMLBackendAdapter()` to accept `workerId`
- [ ] Update `SpawnAdapter` to use worker params
- [ ] Update `AliyunFCAdapter` to use worker params and task-specific base path
- [ ] Update all API routes to use new adapter system
- [ ] Remove BullMQ/Redis files
- [ ] Remove BullMQ/Redis from package.json
- [ ] Remove Redis config from environment
- [ ] Run migrations on dev database
- [ ] Test spawn adapter locally
- [ ] Test FC adapter in production (if available)
- [ ] Update documentation

## Rollback Plan

If issues arise:

1. **Database rollback:**
```sql
ALTER TABLE tasks DROP COLUMN ml_backend_worker_id;
DROP TABLE ml_backend_workers;
```

2. **Code rollback:**
```bash
git checkout feat/deploy-to-aliyun-fc
```

3. **Dependencies:**
- BullMQ/Redis removal is safe because they weren't used in critical path

## Success Criteria

- [ ] All tasks execute successfully using worker-based adapter selection
- [ ] Spawn adapter works for local development
- [ ] Aliyun FC adapter works with `/mnt/oss/tasks/{taskId}` base path
- [ ] No BullMQ or Redis dependencies remaining
- [ ] Database migrations run cleanly
- [ ] All existing tests pass (if any)
- [ ] New tasks reference `ml_backend_worker_id`
- [ ] API can create and manage workers

## Future Enhancements (Out of Scope)

- Admin UI for managing workers
- Worker health checks and monitoring
- Worker load balancing for multiple spawn workers
- Automatic worker selection based on task type
- Worker usage metrics and analytics
