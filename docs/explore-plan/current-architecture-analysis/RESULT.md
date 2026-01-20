# Current Architecture Exploration - Detailed Findings

## Executive Summary

Xenix is a well-structured ML platform with clear separation of concerns across a monorepo architecture. The system demonstrates modern patterns (TanStack Query, Composition API, Hono framework) with some areas showing evolution from legacy patterns. The architecture supports both local development and production deployment on Aliyun FC.

---

## 1. MONOREPO STRUCTURE & PACKAGE ORGANIZATION

### Root-Level Organization

- **pnpm Workspace**: Primary package manager for monorepo
- **4 Primary Packages**:
  1. `@xenix/shared` - Type definitions and Zod schemas
  2. `@xenix/frontend` - Vue 3 + Vite application
  3. `@xenix/backend` - Hono API server
  4. `@xenix/ml-backend` - Standalone ML operations package

### Shared Package (`@xenix/shared`)

```
src/
├── index.ts          # Central export point
├── schemas/          # Zod validation schemas
│   ├── user, project, dataset, task, model, predict
├── types/            # TypeScript type definitions
└── __tests__/
```

**Key Pattern**: Single source of truth for schemas and types - exports both runtime Zod validators and TypeScript types.

---

## 2. FRONTEND ARCHITECTURE

### Tech Stack

- **Framework**: Vite + Vue 3 (Composition API)
- **State Management**: Pinia (lightweight, minimal)
- **Data Fetching**: TanStack Query (Vue Query)
- **API Client**: Hono RPC client
- **UI**: Ant Design Vue + UnoCSS
- **Routing**: Vue Router (explicit route definitions)

### Directory Structure

```
src/
├── main.ts                    # App entry point
├── App.vue                    # Root component
├── router/
│   └── index.ts              # Explicit route definitions
├── stores/
│   └── auth.ts               # Pinia auth store
├── api/
│   └── client.ts             # Hono RPC client instance
├── composables/              # Data fetching hooks
│   ├── useProjects.ts
│   ├── useWorkItems.ts
│   ├── useDatasets.ts
│   ├── useTasks.ts
│   ├── useFormatters.ts
│   └── index.ts
├── components/               # Reusable components
├── views/                    # Page components
│   ├── HomeView.vue
│   ├── work-items/
│   ├── datasets/
│   ├── tasks/
│   └── auth/
├── i18n/                     # Internationalization
├── constants/                # App-level constants
├── styles/                   # SCSS styles
└── __tests__/
```

### Key Patterns

#### 1. **Data Fetching Pattern (TanStack Query)**

```typescript
// Example: useProjects.ts
export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await client.projects.$get({});
      if (!response.ok) {
        const error = (await response.json()) as any;
        throw new Error(error.error || 'Failed to fetch projects');
      }
      return response.json();
    },
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (project) => {
      const response = await client.projects.$post({ json: project });
      // ... error handling
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}
```

**Observations**:

- All data fetching is wrapped in composables (reusable hooks)
- Manual HTTP response checking (is `response.ok`)
- Query invalidation on mutations
- Polling support for long-running tasks (e.g., `useTasks` with 5-second refetch interval)

#### 2. **Hono RPC Client Integration**

```typescript
// api/client.ts
import { hc } from 'hono/client';
import type { AppType } from '@xenix/backend';

export const client = hc<AppType>(apiUrl, {
  headers: () => {
    const token = localStorage.getItem('auth_token');
    return token
      ? { Authorization: `Bearer ${token}` }
      : ({} as Record<string, string>);
  },
});
```

**Observations**:

- Type-safe API client using backend's `AppType` export
- Headers intercepted at request time for auth token injection
- Assumes `AppType` is properly exported from backend

#### 3. **Authentication Pattern**

```typescript
// stores/auth.ts - Pinia store
export const useAuthStore = defineStore("auth", () => {
  const token = ref("");
  const user = ref<any>(null);

  // localStorage initialization
  // login/signup methods
  // logout method
  
  const isAuthenticated = computed(() => !!token.value);
  return { token, user, isAuthenticated, login, signup, logout };
});
```

**Router Guard**:

```typescript
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('auth_token');
  if (to.meta.requiresAuth && !token) {
    next('/auth/signin');
  } else {
    next();
  }
});
```

**Observations**:

- Simple token-based auth stored in localStorage
- Pinia store + localStorage duplication (potential sync issue)
- Router-level auth guard for protected routes
- No automatic token refresh mechanism

#### 4. **Component Pattern**

```typescript
// Example: <script setup lang="ts">
const router = useRouter();
const route = useRoute();
const { t } = useI18n();
const { data: projectsData, isLoading } = useProjects();
const { mutate: createWorkItem, isPending } = useCreateWorkItem();

// Direct template access to reactive data
```

**Observations**:

- All components use `<script setup>` with Composition API
- Heavy use of imported composables
- Simple prop/emit patterns (not extensively used in samples)

---

## 3. BACKEND ARCHITECTURE

### Tech Stack

- **Framework**: Hono (lightweight, fast)
- **Database**: PostgreSQL + DrizzleORM
- **Authentication**: JWT tokens
- **Job Queue**: BullMQ (Redis-backed)
- **File Storage**: Local + Aliyun OSS (configurable)
- **Logging**: Custom logger with structured logging

### Entry Point Analysis

```typescript
// src/index.ts
const app = new Hono();

// Middleware stack
app.use("*", honoLogger());
app.use("*", prettyJSON());
app.use("*", cors({
  origin: config.FRONTEND_URL,
  credentials: true,
}));

// Routes
const routes = app
  .get("/health", ...)
  .route("/auth", authRoutes)
  .route("/projects", projectsRoutes)
  .route("/work-items", workItemsRoutes)
  // ... 8 more routes

// Error handling
app.onError(errorHandler);

// Export type for Hono RPC client
export type AppType = typeof routes;
```

**Key Pattern**: Routes are explicit (no file-based routing), all grouped at entry point.

### Directory Structure

```
src/
├── index.ts                 # App entry, routing, middleware
├── config/
│   └── index.ts            # Zod-validated environment config
├── constants/
│   └── config.ts           # Magic numbers, queue config
├── middleware/
│   ├── auth.ts             # JWT verification + context injection
│   └── errorHandler.ts     # Global error handling
├── routes/                 # API endpoints (explicit)
│   ├── auth.ts
│   ├── projects.ts
│   ├── work-items.ts
│   ├── datasets.ts
│   ├── models.ts
│   ├── tasks.ts
│   ├── train.ts
│   ├── predict.ts
│   ├── download.ts
│   └── obsrv.ts
├── services/               # Business logic
│   ├── AuthService.ts
│   ├── ProjectService.ts
│   ├── WorkItemService.ts
│   ├── DatasetService.ts
│   ├── TaskService.ts
│   ├── ModelService.ts
│   ├── FCInvokeService.ts
│   └── index.ts
├── repositories/           # Data access layer
│   ├── BaseRepository.ts
│   ├── ProjectRepository.ts
│   ├── WorkItemRepository.ts
│   ├── DatasetRepository.ts
│   ├── TaskRepository.ts
│   └── index.ts
├── business/
│   └── ml/                 # ML operations abstraction
│       ├── index.ts        # Exports: batchTrain, singleTrain, predict
│       └── types.ts        # Type definitions
├── adapters/
│   └── ml-backend/         # ML execution strategy (Spawn vs FC)
│       ├── index.ts        # Adapter factory
│       ├── interface.ts    # MLBackendAdapter interface
│       ├── spawn-adapter.ts   # Local process spawning
│       └── aliyun-fc-adapter.ts  # Aliyun FC invocation
├── database/
│   ├── index.ts            # DB client + query builders
│   ├── schema.ts           # Drizzle schema definition
│   ├── migrations/         # Drizzle migrations
│   └── AGENTS.md           # Database documentation
├── jobs/
│   ├── index.ts            # Job exports
│   ├── mlTaskProcessor.ts  # Job processing logic
│   └── mlTaskWorker.ts     # BullMQ worker setup
├── queues/
│   └── index.ts            # BullMQ queue initialization
├── errors/
│   └── AppError.ts         # Custom error classes
├── storage/                # File upload handling
├── utils/
│   ├── logger.ts           # Structured logging
│   ├── taskUtils.ts        # Task utilities
│   └── ...
└── __tests__/
```

### Key Architectural Patterns

#### 1. **Route Pattern (Explicit Routing)**

```typescript
// routes/projects.ts
const projects = new Hono()
  .use("*", authMiddleware)
  .get("/", async (c) => {
    const user = requireAuth(c);
    const projectsList = await projectService.getAllProjects(user.id);
    return c.json(projectsList);
  })
  .post("/", zValidator("json", CreateProjectSchema), async (c) => {
    const user = requireAuth(c);
    const data = c.req.valid("json");
    const project = await projectService.createProject(user.id, data);
    return c.json(project, 201);
  })
  .get("/:id", zValidator("param", ProjectIdParamSchema), async (c) => {
    // ... get single project
  })
  .put("/:id", ..., async (c) => {
    // ... update project
  });

export default projects;
```

**Observations**:

- Hono `zValidator` middleware for request validation (Zod-based)
- Routes are Hono instances composed together
- Per-route middleware (e.g., `authMiddleware`)
- Direct service injection (no DI framework)

#### 2. **Service Layer Pattern**

```typescript
// services/ProjectService.ts
export class ProjectService {
  private projectRepo: ProjectRepository;

  constructor() {
    this.projectRepo = new ProjectRepository();
  }

  async getAllProjects(userId: string) {
    return await this.projectRepo.findByUser(userId);
  }

  async createProject(userId: string, data: CreateProjectDto) {
    // Business logic
    return await this.projectRepo.create({...});
  }
}
```

**Observations**:

- Service classes instantiate repositories directly (tight coupling)
- No dependency injection framework
- Services focused on business logic + orchestration

#### 3. **Repository Pattern**

```typescript
// repositories/BaseRepository.ts
export abstract class BaseRepository<T> {
  constructor(protected table: any) {}

  async findAll(): Promise<T[]> { ... }
  async findById(id: number): Promise<T | null> { ... }
  async create(data: any): Promise<T> { ... }
  async update(id: number, data: any): Promise<T | null> { ... }
  async delete(id: number): Promise<void> { ... }
}

// repositories/ProjectRepository.ts
export class ProjectRepository extends BaseRepository<Project> {
  constructor() {
    super(schema.projects);
  }

  async findByUser(userId: string) {
    return await db
      .select()
      .from(schema.projects)
      .where(eq(schema.projects.createdBy, userId));
  }
}
```

**Observations**:

- Generic base repository with CRUD operations
- Specific repositories extend base with custom queries
- Direct DB client usage (no ORM abstraction beyond Drizzle)

#### 4. **Error Handling Pattern**

```typescript
// errors/AppError.ts
export class AppError extends Error {
  constructor(
    public statusCode: number,
    message: string,
    public name: string
  ) {
    super(message);
  }
}

export class NotFoundError extends AppError {
  constructor(resource: string = "Resource") {
    super(404, `${resource} not found`, "NotFoundError");
  }
}

// middleware/errorHandler.ts
export const errorHandler = (err: Error, c: Context) => {
  if (err instanceof AppError) {
    return c.json(
      {
        code: err.name.replace("Error", "").toUpperCase(),
        error: err.message,
      },
      { status: err.statusCode }
    );
  }

  if (err.name === "ZodError") {
    return c.json(
      {
        code: "VALIDATION_ERROR",
        error: "Validation failed",
        details: (err as any).errors,
      },
      { status: 400 }
    );
  }

  logger.error({ err }, "Unexpected error");
  return c.json(
    { code: "INTERNAL_SERVER_ERROR", error: "Internal Server Error" },
    { status: 500 }
  );
};
```

**Observations**:

- Custom error hierarchy extending Error
- Global error handler catches all exceptions
- Consistent error response format: `{code, error, details?}`
- Automatic Zod error handling

#### 5. **Authentication Pattern**

```typescript
// middleware/auth.ts
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

export async function authMiddleware(c: Context, next: Next) {
  const authHeader = c.req.header("authorization");
  const token = authHeader?.substring(7); // Remove "Bearer "

  const decoded = jwt.verify(token, jwtSecret) as { userId: string };
  const [user] = await db.select().from(schema.users)
    .where(eq(schema.users.id, userId))
    .limit(1);

  c.set("user", user);
  await next();
}

const requireAuth = (c: Context): AuthUser => {
  const user = c.get("user");
  if (!user) throw new UnauthorizedError("Authentication required");
  return user;
};
```

**Observations**:

- JWT token verification with database lookup
- Type-safe context variables via Hono's `ContextVariableMap`
- User lookup on every authenticated request (no caching)
- Helper function `requireAuth()` for route handlers

#### 6. **Database Layer**

```typescript
// database/schema.ts (DrizzleORM)
export const users = pgTable('users', {
  id: uuid('id').defaultRandom().primaryKey(),
  email: text('email').notNull().unique(),
  password: text('password').notNull(),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});

export const projects = pgTable('projects', {
  id: serial('id').primaryKey(),
  createdBy: uuid('created_by').notNull(),
  name: text('name').notNull(),
  description: text('description'),
  // ... other fields
});

export const workItems = pgTable('work_items', {
  id: serial('id').primaryKey(),
  projectId: integer('project_id').notNull(),
  name: text('name').notNull(),
  // ... fields for ML workflow state
});

export const tasks = pgTable('tasks', {
  id: serial('id').primaryKey(),
  workItemId: integer('work_item_id').notNull(),
  type: text('type').notNull(), // 'auto-tune', 'manual-tune', 'predict'
  status: text('status').notNull(), // 'pending', 'running', 'completed', 'failed'
  // ... metadata and results
});
```

**Observations**:

- PostgreSQL with DrizzleORM (type-safe query builder)
- Explicit schema definition with relationships
- JSONB for flexible data storage (model params, feature columns)
- Schema-based migrations

---

## 4. ML OPERATIONS & EXECUTION

### Architecture Overview

```
User → Backend (train/predict routes)
    ↓
MLBackendAdapter (factory pattern)
    ├─→ SpawnAdapter (local dev) → Process spawn → ml-backend Node.js
    └─→ AliyunFCAdapter (production) → FC invoke → Aliyun FC function

ml-backend → Python executor → Python scripts (scikit-learn, XGBoost, etc.)
    ↓
Results → Database & File storage
```

### ML Backend Package (`@xenix/ml-backend`)

```
src/
├── index.ts              # Exports core functions
├── core/
│   ├── batch-train.ts    # GridSearchCV training
│   ├── single-train.ts   # Manual parameter training
│   └── predict.ts        # Batch prediction
├── adapters/             # Execution adapters
│   ├── stdio/            # stdin/stdout communication
│   └── aliyun-fc/        # FC environment setup
├── types/                # Type definitions
├── utils/
│   ├── python-executor.ts  # Spawn Python scripts
│   └── logger.ts           # Database + console logging
└── python/               # Python scripts (not in TypeScript, side-by-side)
```

### Backend ML Integration

```typescript
// backend/src/business/ml/index.ts
export async function batchTrain(options: BatchTrainOptions): Promise<void> {
  const adapter = getMLBackendAdapter();
  await adapter.batchTrain({
    taskId: options.taskId,
    inputFile: options.inputFile,
    model: options.model,
    featureColumns: options.featureColumns,
    targetColumn: options.targetColumn,
    paramGrid: options.paramGrid,
  });
}

// backend/src/adapters/ml-backend/index.ts
export function getMLBackendAdapter(): MLBackendAdapter {
  if (!adapterInstance) {
    adapterInstance = createMLBackendAdapter();
  }
  return adapterInstance;
}

export function createMLBackendAdapter(): MLBackendAdapter {
  const fcAdapter = new AliyunFCAdapter();
  if (fcAdapter.isAvailable()) {
    return fcAdapter; // Production
  }
  return new SpawnAdapter(); // Development
}
```

### Adapter Pattern Deep Dive

#### **SpawnAdapter** (Local Development)

```typescript
// Spawns Node.js child process running ml-backend
const child = spawn('node', [mlBackendPath], {
  stdio: ['pipe', 'pipe', 'pipe'],
});

// Communication protocol: JSON Lines (JSONL)
// - Send: input data (stdin)
// - Receive: logs, status updates, results (stdout)

interface StructuredOutput {
  type: "log" | "status" | "result";
  data: any;
}
```

#### **AliyunFCAdapter** (Production)

```typescript
// Invokes remote FC function asynchronously
const fcInvokeService = new FCInvokeService();
await fcInvokeService.invokeAsync({
  functionName: "ml-batch-train-worker",
  payload: {...},
});

// FC function:
// - Reads from OSS (/mnt/oss/<key>)
// - Writes results directly to database
// - Logs written directly to database
```

### Route Handler (train.ts)

```typescript
// routes/train.ts
.post("/batch-train", zValidator("json", CreateBatchTrainTaskSchema), async (c) => {
  const { datasetId, featureColumns, targetColumn, model, paramGrid, workItemId } 
    = c.req.valid("json");

  // Fetch dataset path from database
  const dataset = await db.select().from(schema.datasets)
    .where(eq(schema.datasets.id, datasetId));

  // Create task record
  const task = await db.insert(schema.tasks).values({
    workItemId,
    type: "auto-tune",
    status: "pending",
    // ... metadata
  }).returning();

  // Invoke ML training (fire and forget)
  await batchTrain({
    taskId: task.id,
    inputFile: dataset.filePath,
    model,
    featureColumns,
    targetColumn,
    paramGrid,
  });

  return c.json(task, 202); // 202 Accepted
});
```

**Observations**:

- Async training: returns 202 Accepted immediately
- Task status tracking in database (pending → running → completed/failed)
- File paths managed via `storage` module
- Model validation delegated to ML backend

### Job Queue Setup

```typescript
// backend/src/queues/index.ts
import { Queue, QueueEvents } from "bullmq";

export const mlTasksQueue = new Queue("ml-tasks", {
  connection: { host, port },
  defaultJobOptions: {
    attempts: 3,
    backoff: { type: "exponential", delay: 2000 },
    removeOnComplete: { age: 24 * 3600 },
    removeOnFail: { age: 7 * 24 * 3600 },
  },
});

mlTasksQueueEvents.on("completed", ({ jobId }) => {
  logger.info({ jobId }, "Job completed");
});
```

**Observations**:

- BullMQ queue initialized but not heavily integrated with routes
- Retry logic configured (3 attempts, exponential backoff)
- Automatic job cleanup based on age
- **Gap**: Routes don't seem to enqueue jobs to BullMQ; operations appear to be fire-and-forget or handled differently

---

## 5. CONFIGURATION & DEPLOYMENT

### Environment Configuration

```typescript
// src/config/index.ts
const configSchema = z.object({
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
  BACKEND_PORT: z.coerce.number().default(3000),
  FRONTEND_URL: z.string().url(),
  DATABASE_URL: z.string().url(),
  REDIS_URL: z.string().url().default('redis://localhost:6379'),
  JWT_SECRET: z.string().min(32),
  MAX_FILE_SIZE: z.coerce.number().default(100 * 1024 * 1024),
  UPLOAD_DIR: z.string().default('./uploads'),
  STORAGE_TYPE: z.enum(['local', 'oss']).default('local'),
  OSS_REGION: z.string().optional(),
  OSS_ACCESS_KEY_ID: z.string().optional(),
  OSS_ACCESS_KEY_SECRET: z.string().optional(),
  OSS_BUCKET: z.string().optional(),
  PYTHON_PATH: z.string().default('/usr/bin/python3'),
  ML_TIMEOUT: z.coerce.number().default(300000),
});

export const config = configSchema.parse(process.env);
```

**Observations**:

- Zod-validated environment variables
- Defaults for development, required for production
- Supports local and OSS storage backends
- Python path configurable per deployment

### Deployment Targets

- **Development**: Local Node.js + PostgreSQL + Redis
- **Production**: Aliyun FC (Functions Compute) + RDS PostgreSQL

### Docker Setup

```yaml
# docker-compose.yml
version: '3.8'
services:
  postgres:
    image: postgres:16
  redis:
    image: redis:7
```

---

## 6. TESTING STRATEGY

### Tools

- **Vitest**: Unit testing framework
- **@vue/test-utils**: Vue component testing
- **Testing patterns**: Not extensively evident in code review

### Test Locations

- `backend/__tests__/`
- `frontend/__tests__/`
- `packages/shared/__tests__/`

**Observations**:

- Test files exist but structure not deeply explored
- No visible E2E testing setup

---

## 7. DATA FLOW VISUALIZATION

### Prepare Flow (Upload Dataset)

```
Frontend (file upload)
  ↓
POST /data/upload (datasets route)
  ↓
Backend: DatasetService.createDataset()
  ↓
Storage: Local or OSS file
  ↓
Database: datasets table entry
  ↓
Frontend: useDatasets() polling
```

### Tune Flow (Auto-Training)

```
Frontend (user clicks "auto tune")
  ↓
POST /train/batch-train (validate input)
  ↓
Backend: Create task record (status='pending')
  ↓
Fire-and-forget: batchTrain() invoked
  ↓
MLBackendAdapter: Spawn or FC invoke
  ↓
Python: auto_tune_model.py (GridSearchCV)
  ↓
ML Backend: Write results to database
  ↓
Frontend: useTasks() polling (5-second interval)
  ↓
Task status updated → View displays results
```

### Predict Flow (Batch Prediction)

```
Frontend (user submits prediction data)
  ↓
POST /predict (with training params + new data)
  ↓
Backend: Create predict task
  ↓
predict() invoked via adapter
  ↓
Python: predict.py (model.predict())
  ↓
Results: Output CSV file
  ↓
Frontend: Download via /download endpoint
```

---

## 8. IDENTIFIED PATTERNS & CONVENTIONS

### ✅ Modern Patterns Implemented

1. **TanStack Query**: Composable data fetching with caching and invalidation
2. **Composition API**: Modern Vue 3 with reusable logic
3. **Type-Safe RPC**: Hono client with backend type export
4. **Zod Validation**: Runtime schema validation + TypeScript types
5. **Explicit Error Classes**: Custom error hierarchy with HTTP semantics
6. **Middleware Stack**: Composable middleware in Hono
7. **Adapter Pattern**: ML backend abstraction (Spawn vs FC)
8. **Repository Pattern**: Data access abstraction with base class
9. **Structured Logging**: Database + console logging with context

### ⚠️ Patterns Showing Evolution

1. **Service Layer**: Services instantiate repositories directly (no DI)
2. **Job Queue**: BullMQ configured but not actively used in routes
3. **Auth State**: Duplication between Pinia store + localStorage
4. **File Paths**: Mixed usage of relative/absolute paths across adapters
5. **Legacy Services**: `src/services/` folder in frontend mentioned as "being phased out"

### 🔴 Architectural Gaps/Concerns

1. **N+1 Queries**: Auth middleware does database lookup per request
2. **Fire-and-Forget ML**: Tasks created but unclear if they're queued or spawned immediately
3. **Adapter Initialization**: Adapter selection happens at startup; can't switch between local/FC during runtime
4. **Database Migrations**: Handled via Drizzle but migration strategy unclear
5. **Error Propagation**: Python errors might not propagate cleanly from FC to database
6. **Token Refresh**: No automatic token refresh mechanism in frontend
7. **Type Safety Gap**: Frontend `any` type usage in auth store (user object)

---

## 9. KEY FILES TO UNDERSTAND ARCHITECTURE

### Frontend

- [packages/frontend/src/main.ts](packages/frontend/src/main.ts) - App bootstrap
- [packages/frontend/src/router/index.ts](packages/frontend/src/router/index.ts) - Route definitions
- [packages/frontend/src/api/client.ts](packages/frontend/src/api/client.ts) - API client setup
- [packages/frontend/src/stores/auth.ts](packages/frontend/src/stores/auth.ts) - Auth state
- [packages/frontend/src/composables/useProjects.ts](packages/frontend/src/composables/useProjects.ts) - Data fetching pattern

### Backend

- [packages/backend/src/index.ts](packages/backend/src/index.ts) - App entry + routing
- [packages/backend/src/config/index.ts](packages/backend/src/config/index.ts) - Configuration
- [packages/backend/src/routes/train.ts](packages/backend/src/routes/train.ts) - ML operations entry
- [packages/backend/src/middleware/auth.ts](packages/backend/src/middleware/auth.ts) - Auth pattern
- [packages/backend/src/adapters/ml-backend/index.ts](packages/backend/src/adapters/ml-backend/index.ts) - ML adapter factory
- [packages/backend/src/services/ProjectService.ts](packages/backend/src/services/ProjectService.ts) - Service pattern
- [packages/backend/src/repositories/BaseRepository.ts](packages/backend/src/repositories/BaseRepository.ts) - Repository pattern

### Shared

- [packages/shared/src/schemas/index.ts](packages/shared/src/schemas/index.ts) - Zod schemas

### ML Backend

- [packages/ml-backend/src/index.ts](packages/ml-backend/src/index.ts) - Package exports
- [packages/ml-backend/src/core/batch-train.ts](packages/ml-backend/src/core/batch-train.ts) - Training logic

---

## 10. ARCHITECTURAL INSIGHTS FOR FUTURE REFACTORING

### Strengths to Preserve

1. ✅ Clear monorepo organization with shared types
2. ✅ Type-safe API layer (Hono RPC client)
3. ✅ Flexible ML backend adapter pattern
4. ✅ Structured error handling
5. ✅ Modern Vue 3 patterns (Composition API, TanStack Query)

### Refactoring Opportunities

1. **Dependency Injection**: Consider introducing a DI container (tsyringe, awilix) to decouple services and repositories
2. **Query Optimization**: Cache user lookups or use request context to avoid N+1 queries
3. **Job Queue Integration**: Actually queue ML tasks in BullMQ instead of fire-and-forget
4. **API Response Wrapper**: Consider consistent response wrapping (success/error envelope) for better error handling
5. **Frontend Auth**: Integrate auth token refresh, remove localStorage duplication
6. **Type Safety**: Replace `any` types in auth store and API responses
7. **Repository Generics**: Improve generic type constraints in BaseRepository
8. **Configuration Validation**: Move config validation to separate module, test against schema

### Future Architecture Improvements

1. **Middleware Ordering**: Ensure error handler is properly ordered (likely should wrap all routes)
2. **Request Context**: Use Hono context map for request-scoped state (avoiding N+1 queries)
3. **API Versioning**: Plan for versioned API endpoints
4. **Rate Limiting**: Consider adding rate limiting middleware
5. **Caching Strategy**: Implement cache layer for frequently accessed data (projects, models, etc.)
6. **Testing Infrastructure**: Set up E2E tests (Playwright) for critical flows
7. **Observability**: Add tracing/APM for production monitoring

---

## Summary Table

| Aspect | Current Implementation | Maturity |
|--------|----------------------|----------|
| Frontend Framework | Vue 3 + Vite | ⭐⭐⭐⭐⭐ |
| Data Fetching | TanStack Query | ⭐⭐⭐⭐⭐ |
| API Client | Hono RPC | ⭐⭐⭐⭐ |
| Authentication | JWT + localStorage | ⭐⭐⭐ |
| Backend Framework | Hono | ⭐⭐⭐⭐⭐ |
| Database Layer | DrizzleORM | ⭐⭐⭐⭐⭐ |
| Error Handling | Custom classes + global handler | ⭐⭐⭐⭐ |
| ML Integration | Adapter factory pattern | ⭐⭐⭐⭐ |
| Job Queue | BullMQ setup | ⭐⭐⭐ (not fully utilized) |
| Testing | Vitest configured | ⭐⭐⭐ (coverage unknown) |
| Deployment | Local + Aliyun FC | ⭐⭐⭐⭐ |
| Type Safety | Good overall | ⭐⭐⭐⭐ (some `any` types) |
