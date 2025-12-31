# API Directory

Nitro server REST API endpoints using file-based routing.

## Routing Convention

Nitro uses file naming to determine HTTP method and route:

| File Name | Method | Route |
|-----------|--------|-------|
| `index.get.ts` | GET | `/api/{folder}` |
| `index.post.ts` | POST | `/api/{folder}` |
| `[id].get.ts` | GET | `/api/{folder}/:id` |
| `[id].put.ts` | PUT | `/api/{folder}/:id` |
| `[id].delete.ts` | DELETE | `/api/{folder}/:id` |

## Directory Structure

```text
api/
├── auto-tune.post.ts      # Start auto-tuning task
├── manual-tune.post.ts    # Start manual-tuning task
├── predict.post.ts        # Start prediction task
├── sync-models.post.ts    # Sync models from Python
├── data/                  # Dataset CRUD
├── models/                # Model management
├── projects/              # Project CRUD
├── work-items/            # Work item management
├── tasks/                 # Task management
├── task/                  # Single task status
├── pythonEnv/             # Python environment
├── obsrv/                 # Observation/logs
└── download/              # File downloads
```

## Endpoint Reference

### ML Operations

#### POST /api/auto-tune

Start GridSearchCV auto-tuning.

```typescript
// Request body
{
  datasetId: string;
  featureColumns: string[];
  targetColumn: string;
  model: string;
  workItemId?: number;
}

// Response
{
  success: boolean;
  taskId: number;
}
```

#### POST /api/manual-tune

Start manual parameter tuning.

```typescript
// Request body
{
  datasetId: string;
  featureColumns: string[];
  targetColumn: string;
  model: string;
  paramGrid: Record<string, any>;
  workItemId?: number;
}
```

#### POST /api/predict

Execute batch prediction.

```typescript
// Request body (multipart/form-data)
{
  file: File;
  model: string;
  tuningTaskId: number;
  trainingDatasetId: string;
  featureColumns: string[];
  targetColumn: string;
}
```

### data/ - Dataset Management

| Endpoint | Description |
|----------|-------------|
| GET /api/data | List all datasets |
| POST /api/data | Upload new dataset |
| GET /api/data/:id | Get dataset details |
| DELETE /api/data/:id | Delete dataset |

### models/ - Model Management

| Endpoint | Description |
|----------|-------------|
| GET /api/models | List available models |
| GET /api/models/:id | Get model details with paramSchema |
| POST /api/models/sync | Sync models from Python scripts |

### projects/ - Project CRUD

| Endpoint | Description |
|----------|-------------|
| GET /api/projects | List all projects |
| POST /api/projects | Create project |
| GET /api/projects/:id | Get project with work items |
| PUT /api/projects/:id | Update project |
| DELETE /api/projects/:id | Delete project |

### work-items/ - Work Item Management

| Endpoint | Description |
|----------|-------------|
| GET /api/work-items | List work items (filter by projectId) |
| POST /api/work-items | Create work item |
| GET /api/work-items/:id | Get work item with tasks |
| PUT /api/work-items/:id | Update work item |
| DELETE /api/work-items/:id | Delete work item |

### tasks/ - Task Management

| Endpoint | Description |
|----------|-------------|
| DELETE /api/tasks/failed | Delete all failed tasks for a work item |

### task/ - Single Task

| Endpoint | Description |
|----------|-------------|
| GET /api/task/:id | Get task status and result |

### pythonEnv/ - Python Environment

| Endpoint | Description |
|----------|-------------|
| GET /api/pythonEnv/status | Check Python environment status |
| POST /api/pythonEnv/setup | Setup Python virtual environment |
| POST /api/pythonEnv/reinstall | Reinstall Python dependencies |

### obsrv/ - Observation

| Endpoint | Description |
|----------|-------------|
| GET /api/obsrv/:id | Get task logs |

### download/

| Endpoint | Description |
|----------|-------------|
| GET /api/download/:id | Download prediction results |

## Handler Pattern

```typescript
import { defineEventHandler, getQuery, readBody } from "h3";
import { db } from "~/server/database";
import * as schema from "~/server/database/schema";

export default defineEventHandler(async (event) => {
  // Get query params
  const query = getQuery(event);

  // Get route params
  const id = event.context.params?.id;

  // Get request body (POST/PUT)
  const body = await readBody(event);

  // Database operations
  const result = await db.select().from(schema.tasks);

  return { success: true, data: result };
});
```

## Error Handling

```typescript
import { createError } from "h3";

// Throw HTTP error
throw createError({
  statusCode: 404,
  message: "Resource not found",
});
```
