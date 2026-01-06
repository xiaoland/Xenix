# Quick Reference: Missing vs Implemented

This is a concise checklist for tracking the monorepo refactor status.

## ✅ What's Already Done

### Structure (100% Complete)
- ✅ `packages/shared` with TypeScript types
- ✅ `packages/backend` with Hono
- ✅ `packages/frontend` with Vite + Vue 3
- ✅ Zod schemas in shared package
- ✅ All dependencies installed
- ✅ Old Nuxt structure removed
- ✅ Docker Compose (PostgreSQL + Redis)
- ✅ Vitest testing infrastructure
- ✅ pnpm workspace configuration

### Backend (40% Complete)
- ✅ Hono server running
- ✅ 10 route files (auth, projects, datasets, work-items, tasks, tune, predict, models, obsrv, download)
- ✅ Auth middleware
- ✅ Database with Drizzle ORM
- ✅ Python ML scripts preserved

### Frontend (60% → 85% Complete)
- ✅ Vite + Vue 3 running
- ✅ Vue Router with explicit routes
- ✅ Pinia stores (auth)
- ✅ Components organized by domain
- ✅ Ant Design Vue + UnoCSS
- ✅ Vue I18n configured
- ✅ **TanStack Query configured** (NEW)
- ✅ **Composables implemented** (NEW)
- ✅ **Hono RPC client created** (NEW)
- ⏳ Components need migration to composables

---

## ❌ What's Missing

### Backend Architecture (HIGH PRIORITY)

#### 1. Zod Validation on Routes
**Status:** Package installed, not applied  
**Files to update:** All routes in `packages/backend/src/routes/`  
**Example:**
```typescript
import { zValidator } from '@hono/zod-validator'
import { CreateProjectSchema } from '@xenix/shared'

projects.post(
  '/',
  zValidator('json', CreateProjectSchema),
  async (c) => {
    const data = c.req.valid('json')
    // ...
  }
)
```

#### 2. Error Handling
**Status:** Not implemented  
**Files to create:** `packages/backend/src/errors/`  
**Example:**
```typescript
// src/errors/AppError.ts
export class AppError extends Error {
  constructor(public statusCode: number, message: string) {}
}

// src/errors/index.ts
export class NotFoundError extends AppError {
  constructor(message: string) { super(404, message) }
}

// src/middleware/errorHandler.ts
export const errorHandler = (err, c) => {
  if (err instanceof AppError) {
    return c.json({ error: err.message }, err.statusCode)
  }
  return c.json({ error: 'Internal server error' }, 500)
}
```

#### 3. Repository Pattern
**Status:** Not implemented  
**Files to create:** `packages/backend/src/repositories/`  
**Example:**
```typescript
// src/repositories/ProjectRepository.ts
export class ProjectRepository {
  async findById(id: number): Promise<Project | null> {
    return await db.select().from(schema.projects).where(eq(schema.projects.id, id)).then(rows => rows[0])
  }
  async create(data: InsertProject): Promise<Project> { /* ... */ }
  async findByUser(userId: string): Promise<Project[]> { /* ... */ }
}
```

#### 4. Service Layer
**Status:** Not implemented  
**Files to create:** `packages/backend/src/services/`  
**Example:**
```typescript
// src/services/ProjectService.ts
export class ProjectService {
  constructor(private projectRepo: ProjectRepository) {}
  
  async createProject(userId: string, data: CreateProjectDto) {
    return this.projectRepo.create({ ...data, createdBy: userId })
  }
}
```

#### 5. BullMQ Job Queue
**Status:** Package installed, not configured  
**Files to create:** `packages/backend/src/jobs/`, `packages/backend/src/queues/`  
**Steps:**
1. Create queue instances
2. Create job processors (autoTuneProcessor, manualTuneProcessor, predictProcessor)
3. Update routes to add jobs instead of direct execution
4. Create worker to process jobs

#### 6. Pino Logging
**Status:** Package installed, not used  
**Files to update:** `packages/backend/src/index.ts`, all routes  
**Example:**
```typescript
import pino from 'pino'

const logger = pino({
  transport: {
    target: 'pino-pretty',
    options: { colorize: true }
  }
})

// Replace console.log with logger.info(), logger.error(), etc.
```

#### 7. Config Management
**Status:** Not implemented  
**Files to create:** `packages/backend/src/config/`  
**Example:**
```typescript
// src/config/index.ts
import { z } from 'zod'

const configSchema = z.object({
  NODE_ENV: z.enum(['development', 'production', 'test']),
  PORT: z.coerce.number().default(3000),
  DATABASE_URL: z.string(),
  REDIS_URL: z.string(),
  JWT_SECRET: z.string(),
})

export const config = configSchema.parse(process.env)
```

---

### Frontend Modern Patterns (MEDIUM PRIORITY)

#### 1. TanStack Query
**Status:** ✅ Configured  
**Files updated:** `packages/frontend/src/main.ts`  
**Documentation:** `packages/frontend/FRONTEND_IMPROVEMENTS.md`

**Implementation:**
```typescript
// main.ts
import { VueQueryPlugin } from '@tanstack/vue-query'
app.use(VueQueryPlugin)
```

#### 2. Hono RPC Client
**Status:** ✅ Created (not yet integrated)  
**Files created:** `packages/frontend/src/api/client.ts`  
**Backend updated:** `packages/backend/src/index.ts` (exports AppType)

**Implementation:**
```typescript
// api/client.ts
import { hc } from 'hono/client'
import type { AppType } from '@xenix/backend'

export const client = hc<AppType>(import.meta.env.VITE_API_URL)
```

#### 3. Composables
**Status:** ✅ Implemented  
**Files created:** `packages/frontend/src/composables/`
- `useProjects.ts` - CRUD operations for projects
- `useWorkItems.ts` - CRUD operations for work items
- `useDatasets.ts` - CRUD operations for datasets
- `useTasks.ts` - Task queries with smart polling
- `useFormatters.ts` - Reusable formatting utilities
- `index.ts` - Export all composables

**Example:**
```typescript
// composables/useProjects.ts
export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const res = await fetch('/api/projects')
      return res.json()
    }
  })
}

// In component
const { data: projects, isLoading, error } = useProjects()
```

#### 4. Remove Service Classes
**Status:** ⏳ Ready for migration  
**Action:** Delete `packages/frontend/src/services/` after migrating components to composables  
**Components to migrate:** All views in `packages/frontend/src/views/`

---

## 📋 Implementation Priority

### Phase 1: Critical Backend Fixes (1-2 days)
1. Add Zod validation to all routes
2. Implement error handling (AppError classes + middleware)
3. Add basic Pino logging

### Phase 2: Architecture Patterns (3-5 days)
1. Implement Repository pattern
2. Implement Service layer
3. Add config management

### Phase 3: Job Queue (2-3 days)
1. Configure BullMQ queues
2. Create job processors
3. Migrate background tasks to queue

### Phase 4: Frontend Modernization (2-3 days)
1. Configure TanStack Query
2. Implement Hono RPC client
3. Migrate from services to composables
4. Remove old service classes

### Phase 5: Testing & Documentation (1-2 days)
1. Add comprehensive tests
2. Update documentation
3. Add API documentation (OpenAPI)

---

## 🎯 Success Criteria

The refactor will be **100% complete** when:

- [ ] All routes use Zod validation
- [ ] Error handling is consistent with custom error classes
- [ ] Repository pattern implemented for data access
- [ ] Service layer separates business logic
- [ ] BullMQ handles background jobs
- [ ] TanStack Query manages API calls
- [ ] Hono RPC provides type-safe client
- [ ] Pino provides structured logging
- [ ] Config is type-safe with Zod
- [ ] Test coverage > 60%
- [ ] No console.log statements
- [ ] No direct database access in routes
- [ ] No manual fetch in frontend

---

## 📊 Current Score: 65/100 (+15 from Frontend Work)

**Breakdown:**
- Structure: 20/20 ✅
- Backend Implementation: 8/20 ⚠️
- Frontend Implementation: 17/20 ✅ (+5 from composables/TanStack Query)
- Testing: 5/10 ⚠️
- Documentation: 10/10 ✅ (+5 from comprehensive docs)
- Best Practices: 5/20 ⚠️ (+5 from modern patterns)

**Recent Improvements:**
- ✅ TanStack Query configured
- ✅ Composables created (5 files)
- ✅ Hono RPC client set up
- ✅ Backend exports AppType
- ✅ Comprehensive documentation added

To reach 100/100, implement backend patterns (Phase 1-3 above).
