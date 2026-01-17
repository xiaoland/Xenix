# Refactor Plan v2: HTTP-based ML Backend Deployments

## Overview

Replace the adapter-based system with a simple HTTP-based deployment system where ml-backend runs as an HTTP server that returns immediately and stores results in the filesystem.

**Branch:** `claude/replace-bullmq-tasks-table-bxLPe`
**Base:** Previous refactoring (adapter-based)

## Key Architectural Changes

### Before (Adapter-based):
```
Backend → Adapter (Spawn/FC) → ML Backend → Stores results in DB
```

### After (HTTP-based):
```
Backend → HTTP POST to deployment URL → ML Backend HTTP Server
                                         ↓
                                   Returns 202 immediately
                                         ↓
                              Stores results in base-path/result.json
                                         ↓
Frontend polls task → Backend checks OSS/filesystem → Updates task table
```

## Database Schema Changes

### Rename: ml_backend_workers → ml_backend_deployments

```sql
-- Rename table
ALTER TABLE ml_backend_workers RENAME TO ml_backend_deployments;

-- Update column names
ALTER TABLE ml_backend_deployments RENAME COLUMN adapter TO deployment_type;
ALTER TABLE ml_backend_deployments RENAME COLUMN adapter_params TO deployment_params;

-- Update tasks table foreign key
ALTER TABLE tasks RENAME COLUMN ml_backend_worker_id TO ml_backend_deployment_id;

-- Update indexes
DROP INDEX IF EXISTS idx_ml_backend_workers_adapter;
DROP INDEX IF EXISTS idx_ml_backend_workers_default;
CREATE INDEX idx_ml_backend_deployments_type ON ml_backend_deployments(deployment_type);
CREATE INDEX idx_ml_backend_deployments_default ON ml_backend_deployments(is_default) WHERE is_default = true;
DROP INDEX IF EXISTS idx_tasks_worker;
CREATE INDEX idx_tasks_deployment ON tasks(ml_backend_deployment_id);
```

### New deployment_params structure

```typescript
interface DeploymentParams {
  apiUrl: string;  // HTTP endpoint URL
  proxy?: string;  // 'frontend://this' | http proxy URL
  basePath?: string;  // Base path for file operations
}
```

## ML Backend HTTP Server

Create a simple Flask/FastAPI server that wraps ml-backend:

**File:** `packages/ml-backend/server.py`

```python
from flask import Flask, request, jsonify
import json
import os
import threading
from ml_backend.config import Config
from ml_backend.controllers import batch_train, single_train, predict
from ml_backend.utils import init_logger, log

app = Flask(__name__)

def execute_task_async(operation, data, base_path, task_id):
    """Execute ML task in background thread"""
    try:
        # Set base path
        if base_path:
            Config.set_base_path(base_path)

        # Initialize logger
        init_logger(task_id)
        Config.ensure_directories()

        # Execute operation
        result = None
        if operation == "batch-train":
            result = batch_train(BatchTrainInput(**data))
        elif operation == "single-train":
            result = single_train(SingleTrainInput(**data))
        elif operation == "predict":
            result = predict(PredictInput(**data))

        # Store result
        result_file = os.path.join(Config.BASE_PATH, "result.json")
        with open(result_file, 'w') as f:
            json.dump({
                "status": "completed",
                "result": result.model_dump()
            }, f)

    except Exception as e:
        # Store error
        result_file = os.path.join(Config.BASE_PATH, "result.json")
        with open(result_file, 'w') as f:
            json.dump({
                "status": "failed",
                "error": str(e)
            }, f)

@app.route('/execute', methods=['POST'])
def execute():
    """Execute ML task endpoint - returns immediately"""
    data = request.json

    operation = data.get('operation')
    task_data = data.get('data', {})
    base_path = data.get('basePath')
    task_id = task_data.get('task_id')

    # Start background thread
    thread = threading.Thread(
        target=execute_task_async,
        args=(operation, task_data, base_path, task_id)
    )
    thread.daemon = True
    thread.start()

    # Return immediately
    return jsonify({"status": "accepted", "task_id": task_id}), 202

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
```

## Backend Changes

### Remove Adapters

Delete:
- `packages/backend/src/adapters/ml-backend/spawn-adapter.ts`
- `packages/backend/src/adapters/ml-backend/aliyun-fc-adapter.ts`
- `packages/backend/src/adapters/ml-backend/interface.ts`
- `packages/backend/src/adapters/ml-backend/index.ts` (entire directory)

### New HTTP Client

**File:** `packages/backend/src/services/MLBackendService.ts`

```typescript
export class MLBackendService {
  async executeTask(deployment: MLBackendDeployment, operation: string, data: any) {
    const taskId = data.task_id;
    const basePath = this.getBasePath(deployment, taskId);

    const payload = {
      operation,
      data,
      basePath
    };

    // Make HTTP POST request
    const response = await fetch(deployment.deployment_params.apiUrl + '/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      // Handle proxy if configured
      // ...proxy logic...
    });

    if (response.status !== 202) {
      throw new Error(`ML backend returned ${response.status}`);
    }

    return { accepted: true, taskId };
  }

  async checkResult(deployment: MLBackendDeployment, taskId: number) {
    const basePath = this.getBasePath(deployment, taskId);
    const resultPath = `${basePath}/result.json`;

    // Check if result exists (OSS or local filesystem)
    // Parse and return result
    // ...
  }
}
```

### Result Polling

**File:** `packages/backend/src/routes/tasks.ts`

```typescript
router.get('/:id', async (c) => {
  const taskId = parseInt(c.req.param('id'));

  // Get task from database
  const task = await taskRepo.findById(taskId);

  // If task is pending/running, check for results
  if (task.status === 'running' || task.status === 'pending') {
    // Fire-and-forget result check
    setImmediate(async () => {
      const deployment = await deploymentRepo.findById(task.ml_backend_deployment_id);
      const result = await mlBackendService.checkResult(deployment, taskId);

      if (result) {
        await taskRepo.update(taskId, {
          status: result.status,
          result: result.result,
          error: result.error,
          endAt: new Date()
        });
      }
    });
  }

  return c.json(task);
});
```

## Deployment Types

```typescript
type DeploymentType = 'http' | 'http-proxy-frontend';

interface MLBackendDeployment {
  id: number;
  name: string;
  deployment_type: DeploymentType;
  deployment_params: {
    apiUrl: string;
    proxy?: string;  // HTTP proxy URL or 'frontend://this'
    basePath?: string;
  };
  is_default: boolean;
  is_active: boolean;
}
```

## Migration Strategy

1. Rename tables and columns
2. Update seed data to use HTTP deployment type
3. Update all code references from worker → deployment
4. Create HTTP server for ml-backend
5. Replace adapter calls with HTTP calls
6. Implement result polling mechanism

## Implementation Steps

1. Create migration to rename tables
2. Update TypeScript types (worker → deployment)
3. Update repositories
4. Create ML backend HTTP server
5. Create MLBackendService for HTTP calls
6. Update business logic to use HTTP service
7. Implement result polling in task routes
8. Remove adapter code
9. Remove fc_handler.py
10. Test end-to-end

## Testing

- Local: Run ml-backend HTTP server on localhost:8000
- Production: Deploy ml-backend as HTTP service to Aliyun FC or container
- Test result polling mechanism
- Verify fire-and-forget execution
