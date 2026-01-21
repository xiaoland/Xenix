# `@xenix/backend` Architecture

> Last updated at UTC+8 2026-01-15 13:10

## Overview

REST API server handling authentication, data management, ML operations, and file uploads. Routes are explicitly defined at app entry. Business logic flows through Services → Repositories → Database.

> Framework: Hono + Node.js
> Database: PostgreSQL + DrizzleORM

## Directory Structure

```
src/
├── index.ts              # App entry, middleware, routing
├── config/index.ts       # Zod-validated environment config
├── constants/config.ts   # Magic numbers, timeouts, limits
├── middleware/
│   ├── auth.ts          # JWT verification + context injection
│   └── errorHandler.ts  # Global error handling
├── routes/              # Explicit route handlers
│   ├── auth.ts          # /auth (signin, signup)
│   ├── projects.ts      # /projects CRUD
│   ├── work-items.ts    # /work-items CRUD
│   ├── datasets.ts      # /data upload, list
│   ├── models.ts        # /models (metadata)
│   ├── tasks.ts         # /tasks (status, cleanup)
│   ├── train.ts         # /train (batch-train, manual-train)
│   ├── predict.ts       # /predict (batch prediction)
│   ├── download.ts      # /download (results)
│   └── obsrv.ts         # /obsrv (observability)
├── services/            # Business logic
│   ├── AuthService.ts
│   ├── ProjectService.ts
│   ├── WorkItemService.ts
│   ├── DatasetService.ts
│   ├── TaskService.ts
│   ├── ModelService.ts
│   ├── MLBackendService.ts
│   └── index.ts
├── repositories/        # Data access layer
│   ├── BaseRepository.ts
│   ├── ProjectRepository.ts
│   ├── WorkItemRepository.ts
│   ├── DatasetRepository.ts
│   ├── TaskRepository.ts
│   └── index.ts
├── business/ml/         # ML operations abstraction
│   ├── index.ts         # Exports: batchTrain, singleTrain, predict
│   └── types.ts         # Type definitions
├── adapters/ml-backend/ # ML execution strategy selector
│   ├── index.ts         # Adapter factory
│   ├── interface.ts     # MLBackendAdapter interface
│   ├── spawn-adapter.ts # Local process spawn
│   └── aliyun-fc-adapter.ts # Aliyun FC invoke
├── database/
│   ├── index.ts         # DB connection + query builders
│   ├── schema.ts        # DrizzleORM table definitions
│   └── migrations/      # Drizzle migrations
├── errors/
│   └── AppError.ts      # Custom error classes (NotFound, Unauthorized, etc.)
├── jobs/
│   ├── index.ts         # Job exports
│   ├── mlTaskProcessor.ts
│   └── mlTaskWorker.ts
├── queues/
│   └── index.ts         # BullMQ queue initialization
├── storage/             # File upload/download handling
├── utils/
│   ├── logger.ts        # Structured logging
│   ├── taskUtils.ts
│   └── ...
└── __tests__/
```

## Request Lifecycle

```
HTTP Request
  ↓
Middleware Stack:
  1. honoLogger() - log request
  2. prettyJSON() - format responses
  3. cors() - cross-origin
  4. authMiddleware (per route) - JWT verify
  ↓
Route Handler:
  1. zValidator - validate input (Zod)
  2. requireAuth() - get user from context
  3. Service method - business logic
  ↓
Service (e.g., ProjectService):
  1. Repository call - data access
  2. Business logic - validation, transformation
  3. Return result
  ↓
Repository (e.g., ProjectRepository):
  1. Build DrizzleORM query
  2. Execute query
  3. Return data
  ↓
Response:
  1. c.json(data) or c.json(data, status)
  2. Global errorHandler catches exceptions
  3. Return {code, error, details?} on error
```

## Key Patterns

**Route Definition**

- Routes are Hono instances composed at index.ts
- `zValidator` middleware for input validation (Zod schemas from @xenix/shared)
- `requireAuth()` extracts user from context
- HTTP semantics: `c.json(data)` returns 200, `c.json(data, status)` returns custom status

**Service Layer**

- Services instantiate repositories (consider DI in future)
- Contain business logic beyond query wrappers
- Called from route handlers

**Repository Pattern**

- Extend BaseRepository for standard CRUD
- Add custom queries for complex data access
- Use DrizzleORM query builder for type safety

**Error Handling**

- Custom error classes extend AppError
- Global error handler catches all exceptions
- Response format: `{code, error, details?}`
- Automatic Zod validation error handling

**Authentication**

- JWT verification + user lookup per request (N+1 concern)
- User stored in Hono context via middleware
- Type-safe context injection via Hono interface

**Database Schema**

- DrizzleORM for type-safe schema definition
- JSONB columns for flexible fields (metadata, params)
- Migrations via Drizzle Kit

**ML Operations Flow**

- Task created immediately (status=pending)
- ML operation fired asynchronously via MLBackendService
- Returns 201 Created (not waiting for result)
- MLBackendService handles both local HTTP and OSS-based deployments

**Configuration**

- Zod-validated environment variables at startup
- Throws error if missing/invalid config
- Type-safe config object
  }

  async createProject(userId: string, data: CreateProjectDto) {
    // Business logic
    const project = await this.projectRepo.create({...});
    return project;
  }
}

```

Type-safe context injection:
```typescript
export interface AuthUser {
  id: string;
  email: string;
  phone?: string | null;
}

declare module "hono" {
  interface ContextVariableMap {
    user: AuthUser;
  }
}
  const token = c.req.header("authorization")?.substring(7);
  const decoded = jwt.verify(token, secret) as { userId: string };
  const [user] = await db.select().from(schema.users)
    .where(eq(schema.users.id, decoded.userId));
  c.set("user", user);
  await next();
}

const requireAuth = (c: Context): AuthUser => {
  const user = c.get("user");
  if (!user) throw new UnauthorizedError("Auth required");
  return user;
};
```

Key points:

- JWT token extracted from Authorization header
- User lookup per request (N+1 concern - consider caching)
- Type-safe context injection via Hono

### 6. Database Schema

```typescript
// database/schema.ts
export const users = pgTable('users', {
  id: uuid('id').defaultRandom().primaryKey(),
  email: text('email').notNull().unique(),
  password: text('password').notNull(),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});

export const tasks = pgTable('tasks', {
  id: serial('id').primaryKey(),
  workItemId: integer('work_item_id').notNull(),
  type: text('type').notNull(), // 'auto-tune', 'manual-tune', 'predict'
  status: text('status').notNull(), // 'pending', 'running', 'completed', 'failed'
  modelName: text('model_name'),
  inputFilePath: text('input_file_path'),
  outputFilePath: text('output_file_path'),
  errorMessage: text('error_message'),
  resultMetadata: jsonb('result_metadata'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});
```

Key points:

- DrizzleORM for type-safe schema
- JSONB for flexible fields (metadata, results)
- Migrations handled via Drizzle Kit

### 7. ML Operations Flow

```typescript
// routes/train.ts
.post("/batch-train", zValidator("json", CreateBatchTrainTaskSchema), async (c) => {
  const { datasetId, featureColumns, targetColumn, model, paramGrid } = c.req.valid("json");

  // Create task record
  const task = await db.insert(schema.tasks).values({
    workItemId,
    type: "auto-tune",
    status: "pending",
  }).returning();

  // Fire-and-forget ML operation
  batchTrain({
    taskId: task.id,
    inputFile: dataset.filePath,
    model,
    featureColumns,
    targetColumn,
    paramGrid,
  }).catch(err => logger.error(err));

  return c.json(task, 202); // 202 Accepted
});

// business/ml/index.ts
export async function batchTrain(options: BatchTrainOptions): Promise<void> {
  const adapter = getMLBackendAdapter();
  await adapter.batchTrain({...});
}

// adapters/ml-backend/index.ts
export function getMLBackendAdapter(): MLBackendAdapter {
  const fcAdapter = new AliyunFCAdapter();
  if (fcAdapter.isAvailable()) return fcAdapter; // Production
  return new SpawnAdapter(); // Dev
}
```

Key points:

- Task created immediately (status=pending)
- ML operation fired asynchronously
- Returns 202 Accepted (not waiting for result)
- Adapter selected at startup (can't switch during runtime)

### 8. Configuration (Zod-Validated)

```typescript
// config/index.ts
const configSchema = z.object({
  NODE_ENV: z.enum(['development', 'production', 'test']),
  BACKEND_PORT: z.coerce.number().default(3000),
  FRONTEND_URL: z.string().url(),
  DATABASE_URL: z.string().url(),
  REDIS_URL: z.string().url().default('redis://localhost:6379'),
  JWT_SECRET: z.string().min(32),
  OSS_REGION: z.string().optional(),
  // ...
});

export const config = configSchema.parse(process.env);
```

Key points:

- Environment variables validated at startup
- Throws on missing/invalid config
- Type-safe config object

## ML Operations

### MLBackendService

MLBackendService provides a unified HTTP-based interface for communicating with ML backend deployments.

```text
User Request
  ↓
Route Handler (/train, /predict)
  ↓
MLBackendService.execute()
  ↓
POST {deployment.apiUrl}/execute
  - operation: 'batch-train' | 'single-train' | 'predict'
  - data: { task_id, input_file, model, ... }
  ↓
ML Backend (local or cloud):
  - Processes request asynchronously
  - Writes results to storage (local or OSS)
  - Updates task status in database
```

### Deployment Types

#### Local Deployment (storage='local')

- ML backend runs as HTTP server on localhost
- Results fetched via HTTP: `GET {apiUrl}/tasks/{taskId}/result`
- Used for development

#### OSS Deployment (storage='oss')

- ML backend runs on Aliyun FC or other cloud infrastructure
- Results stored in OSS bucket: `tasks/{taskId}/result.json`
- MLBackendService fetches results directly from OSS
- Used for production

## Job Queue (BullMQ)

```typescript
// queues/index.ts
export const mlTasksQueue = new Queue("ml-tasks", {
  connection: { host, port },
  defaultJobOptions: {
    attempts: 3,
    backoff: { type: "exponential", delay: 2000 },
    removeOnComplete: { age: 24 * 3600 },
  },
});
```

Status: Configured but not actively integrated with routes. ML tasks are currently fire-and-forget, not queued.

## Development & Deployment

For setup and deployment instructions, see:

- [DEVELOPMENT.md](../../DEVELOPMENT.md) - Development setup, testing, conventions
- [DEPLOYMENT.md](../../DEPLOYMENT.md) - Production deployment, Aliyun FC, security

## Known Issues

⚠️ **N+1 Queries**: Auth middleware does user lookup per request
⚠️ **Fire-and-Forget ML**: Tasks created but unclear full tracking
⚠️ **BullMQ Unused**: Queue configured but routes don't enqueue jobs
⚠️ **No DI Container**: Services instantiate repositories directly
⚠️ **Error Propagation**: Python errors might not reach frontend cleanly
