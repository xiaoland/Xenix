# Ruthless Monorepo Refactor: Modern Full-Stack Architecture

## Current State (Problems Identified)

- ❌ **Mixed concerns**: Nuxt.js handles both frontend and backend
- ❌ **File-based routing**: Implicit and hard to trace
- ❌ **No type safety**: Frontend/backend types not shared
- ❌ **Poor separation**: Direct DB access in API handlers
- ❌ **No job queue**: Database polling for background tasks
- ❌ **Weak validation**: Inconsistent input validation
- ❌ **Manual API client**: Hand-written services with `$fetch`
- ❌ **No testing**: No test infrastructure
- ❌ **Poor error handling**: Inconsistent error responses
- ❌ **Spawning Python**: Process spawning is inefficient

## Target State (Modern Best Practices)

### Architecture

- **Monorepo**: `packages/app`, `packages/server`, `packages/shared`
- **End-to-end Type Safety**: Hono RPC (similar to tRPC but Hono-native)
- **Validation**: Zod schemas everywhere (shared between frontend/backend)
- **Frontend**: Vite + Vue 3 + TanStack Query + Pinia
- **Backend**: Hono + Drizzle ORM + Repository Pattern + DI
- **Job Queue**: BullMQ for background ML tasks
- **Testing**: Vitest for both frontend and backend
- **Logging**: Pino with structured logging
- **Python**: Keep but optimize with better process management

## New Architecture

### Package Structure

```
Xenix/
├── packages/
│   ├── shared/              # Shared code between frontend/backend
│   │   ├── src/
│   │   │   ├── schemas/     # Zod validation schemas
│   │   │   ├── types/       # Shared TypeScript types
│   │   │   ├── constants/   # Shared constants (model names, etc.)
│   │   │   └── utils/       # Shared utilities
│   │   ├── package.json
│   │   └── tsconfig.json
│   │
│   ├── app/                 # Frontend application
│   │   ├── src/
│   │   │   ├── main.ts
│   │   │   ├── App.vue
│   │   │   ├── components/  # Vue components (Composition API)
│   │   │   ├── pages/       # Page components
│   │   │   ├── router/      # Vue Router config
│   │   │   ├── stores/      # Pinia stores
│   │   │   ├── composables/ # Composition functions
│   │   │   ├── api/         # Auto-generated RPC client
│   │   │   ├── styles/      # SCSS styles
│   │   │   └── i18n/        # Internationalization
│   │   ├── index.html
│   │   ├── vite.config.ts
│   │   ├── uno.config.ts
│   │   └── package.json
│   │
│   └── server/              # Backend API
│       ├── src/
│       │   ├── index.ts     # Hono app entry
│       │   ├── app.ts       # Hono app setup
│       │   ├── routes/      # API routes (explicit, grouped)
│       │   ├── middleware/  # Auth, CORS, error handling
│       │   ├── repositories/# Data access layer (Repository pattern)
│       │   ├── services/    # Business logic layer
│       │   ├── database/    # Drizzle schema & migrations
│       │   ├── jobs/        # BullMQ job processors
│       │   ├── ml/          # ML business logic & Python
│       │   ├── utils/       # Server utilities
│       │   └── config/      # Configuration management
│       ├── drizzle.config.ts
│       └── package.json
│
├── data/                    # Model parameters (shared)
├── datasets/                # Uploaded datasets (shared)
├── uploads/                 # File uploads (shared)
├── public/                  # Static assets
├── package.json             # Root workspace config
├── pnpm-workspace.yaml      # pnpm workspace
├── tsconfig.json            # Base TypeScript config
└── .env.example             # Environment variables template
```

## Implementation Strategy

### Phase 1: Foundation - Shared Package

**Purpose**: Eliminate duplicate types, enable end-to-end type safety

1. **Create `packages/shared`**
   - Setup package.json with TypeScript
   - Create Zod schemas for all entities:
     - `UserSchema`, `ProjectSchema`, `DatasetSchema`
     - `TaskSchema`, `WorkItemSchema`, `ModelMetadataSchema`
     - Request/Response schemas for all API endpoints
   - Export TypeScript types from Zod schemas
   - Create shared constants (model names, task types, etc.)
   - Create shared utilities (date formatting, validation helpers)

2. **Benefits**
   - Single source of truth for data structures
   - Runtime validation + TypeScript types from one definition
   - No manual type sync between frontend/backend
   - Compile-time errors if API contract changes

### Phase 2: Backend - Hono with Clean Architecture

1. **Dependencies**

   ```json
   {
     "hono": "^4.7.0",
     "@hono/node-server": "^1.13.7",
     "@hono/zod-validator": "^0.4.1",
     "drizzle-orm": "^0.45.1",
     "drizzle-kit": "^0.31.8",
     "pg": "^8.13.1",
     "zod": "^3.24.1",
     "bullmq": "^5.38.1",
     "ioredis": "^5.4.2",
     "pino": "^9.7.0",
     "pino-pretty": "^13.0.0",
     "jsonwebtoken": "^9.0.3",
     "bcrypt": "^6.0.0",
     "@types/*": "latest"
   }
   ```

2. **Architecture Layers**

   **a) Repository Layer** (`src/repositories/`)
   - Abstract database access
   - One repository per entity (UserRepository, ProjectRepository, etc.)
   - Type-safe queries with Drizzle
   - Example:

     ```typescript
     export class ProjectRepository {
       async findById(id: number): Promise<Project | null>
       async create(data: InsertProject): Promise<Project>
       async update(id: number, data: Partial<Project>): Promise<Project>
       async delete(id: number): Promise<void>
       async findByUser(userId: string): Promise<Project[]>
     }
     ```

   **b) Service Layer** (`src/services/`)
   - Business logic only
   - Uses repositories for data access
   - No HTTP concerns (req/res)
   - Throws domain exceptions
   - Example:

     ```typescript
     export class ProjectService {
       constructor(
         private projectRepo: ProjectRepository,
         private workItemRepo: WorkItemRepository
       ) {}
       
       async createProject(userId: string, data: CreateProjectDto) {
         // Business logic here
         return this.projectRepo.create({ ...data, createdBy: userId })
       }
     }
     ```

   **c) Route Handlers** (`src/routes/`)
   - HTTP layer only
   - Input validation with Zod
   - Call services
   - Transform responses
   - Example:

     ```typescript
     const projectRoutes = new Hono<{ Variables: AppVariables }>()
       .post(
         '/',
         zValidator('json', CreateProjectSchema),
         async (c) => {
           const user = c.get('user')
           const data = c.req.valid('json')
           const project = await projectService.createProject(user.id, data)
           return c.json(project, 201)
         }
       )
     ```

3. **Dependency Injection**
   - Create DI container (`src/di.ts`)
   - Register all repositories, services
   - Pass to Hono context
   - No global singletons (except DB connection pool)

4. **Middleware Stack**

   ```typescript
   app.use('*', cors())
   app.use('*', pinoLogger())
   app.use('/api/*', authMiddleware())  // Validates JWT, attaches user
   app.use('*', errorHandler())         // Catches all errors, formats response
   ```

5. **Error Handling**
   - Custom error classes:

     ```typescript
     class AppError extends Error {
       constructor(
         public statusCode: number,
         message: string,
         public code?: string
       ) {}
     }
     
     class NotFoundError extends AppError {}
     class UnauthorizedError extends AppError {}
     class ValidationError extends AppError {}
     ```

   - Error middleware transforms to HTTP response

6. **Background Jobs with BullMQ**
   - Replace database polling with Redis queue
   - Create job queues:
     - `ml-auto-tune` queue
     - `ml-manual-tune` queue  
     - `ml-predict` queue
   - Job processors in `src/jobs/`:

     ```typescript
     // src/jobs/autoTuneProcessor.ts
     export const autoTuneProcessor = async (job: Job<AutoTuneJobData>) => {
       const { taskId, datasetId, model, paramGrid } = job.data
       // Execute Python script
       // Update task status via repository
       // Store results
     }
     ```

   - API endpoint adds job to queue, returns task ID immediately

7. **Python Integration** (`src/ml/`)
   - Keep existing Python scripts
   - Improve executor:
     - Use worker pool instead of spawning each time
     - Better error handling
     - Timeout management
     - Process health checks

8. **Logging with Pino**
   - Structured logging everywhere
   - Request/response logging
   - Job execution logging
   - OpenTelemetry compatible format

9. **Configuration Management**
   - Type-safe config from env:

     ```typescript
     const configSchema = z.object({
       NODE_ENV: z.enum(['development', 'production', 'test']),
       PORT: z.coerce.number().default(3001),
       DATABASE_URL: z.string(),
       REDIS_URL: z.string(),
       JWT_SECRET: z.string(),
     })
     
     export const config = configSchema.parse(process.env)
     ```

### Phase 3: Frontend - Vite + Vue with Modern Patterns

1. **Dependencies**

   ```json
   {
     "vue": "^3.5.25",
     "vite": "^6.0.7",
     "@vitejs/plugin-vue": "^5.2.1",
     "vue-router": "^4.6.4",
     "pinia": "^2.3.1",
     "@tanstack/vue-query": "^5.64.3",
     "ant-design-vue": "^4.2.6",
     "unocss": "^66.5.10",
     "@unocss/preset-icons": "^66.5.10",
     "sass": "^1.97.0",
     "vue-i18n": "^10.0.9",
     "zod": "^3.24.1",
     "@vueuse/core": "^12.4.0",
     "axios": "^1.8.0"
   }
   ```

2. **RPC Client** (Hono RPC)
   - Hono's native RPC client for type-safe API calls
   - Auto-generated from backend routes
   - Example:

     ```typescript
     // Automatically get types from backend
     import { hc } from 'hono/client'
     import type { AppType } from '@xenix/server'
     
     const client = hc<AppType>('http://localhost:3001')
     
     // Fully type-safe!
     const projects = await client.api.projects.$get()
     const data = await projects.json()  // Type: Project[]
     ```

3. **TanStack Query Integration**
   - Replace manual `useApi()` composable
   - Built-in caching, refetching, optimistic updates
   - Example:

     ```typescript
     // composables/useProjects.ts
     export function useProjects() {
       return useQuery({
         queryKey: ['projects'],
         queryFn: async () => {
           const res = await client.api.projects.$get()
           return res.json()
         }
       })
     }
     
     // In component
     const { data: projects, isLoading, error } = useProjects()
     ```

4. **Remove Unnecessary Abstractions**
   - ❌ Delete `services/` directory (replaced by RPC client + TanStack Query)
   - ❌ Delete `useApi()` composable (replaced by RPC client)
   - ✅ Keep `composables/` for reusable logic (not API calls)
   - ✅ Keep `stores/` only for global state (not API data)

5. **Pinia Stores - Minimal Usage**
   - Only for true global state:
     - Auth state (user, token)
     - UI state (sidebar open/closed, theme)
   - NOT for API data (use TanStack Query instead)
   - Example:

     ```typescript
     // stores/auth.ts
     export const useAuthStore = defineStore('auth', () => {
       const token = ref<string | null>(localStorage.getItem('token'))
       const user = ref<User | null>(null)
       
       async function login(credentials: LoginDto) {
         const res = await client.api.auth.signin.$post({ json: credentials })
         const data = await res.json()
         token.value = data.token
         user.value = data.user
         localStorage.setItem('token', data.token)
       }
       
       function logout() {
         token.value = null
         user.value = null
         localStorage.removeItem('token')
       }
       
       return { token, user, login, logout }
     })
     ```

6. **Vue Router - Explicit Routes**
   - No file-based routing
   - Explicit route definitions:

     ```typescript
     const routes = [
       { path: '/', component: () => import('@/pages/HomePage.vue') },
       { path: '/signin', component: () => import('@/pages/SignInPage.vue') },
       { 
         path: '/projects', 
         component: () => import('@/pages/ProjectsPage.vue'),
         meta: { requiresAuth: true }
       },
       // ... all routes explicitly defined
     ]
     ```

   - Auth guard:

     ```typescript
     router.beforeEach((to, from, next) => {
       const auth = useAuthStore()
       if (to.meta.requiresAuth && !auth.token) {
         next('/signin')
       } else {
         next()
       }
     })
     ```

7. **Component Structure**
   - Composition API only (no Options API)
   - `<script setup lang="ts">`
   - Proper prop validation with Zod:

     ```typescript
     const props = defineProps<{
       project: z.infer<typeof ProjectSchema>
     }>()
     ```

   - Prefer primitives over "smart" components

8. **Form Handling**
   - Use `@vueuse/core` for form state
   - Zod validation from `@xenix/shared`
   - Example:

     ```typescript
     const formData = reactive<CreateProjectDto>({
       name: '',
       description: ''
     })
     
     const { mutate: createProject, isPending } = useMutation({
       mutationFn: async (data: CreateProjectDto) => {
         const res = await client.api.projects.$post({ json: data })
         return res.json()
       },
       onSuccess: () => {
         queryClient.invalidateQueries({ queryKey: ['projects'] })
         router.push('/projects')
       }
     })
     ```

9. **i18n Setup**
   - Vue I18n 10 (Composition API)
   - Keep existing translations
   - Example:

     ```typescript
     const { t } = useI18n()
     ```

10. **Development Experience**
    - Vite config optimizations
    - Hot module replacement
    - Component auto-import (unplugin-vue-components)
    - Auto-import composables (unplugin-auto-import)

### Phase 4: Testing Infrastructure

1. **Shared Package Tests**
   - Test Zod schemas
   - Test shared utilities
   - Example:

     ```typescript
     describe('ProjectSchema', () => {
       it('validates correct project data', () => {
         const valid = { name: 'Test', description: 'Desc' }
         expect(() => ProjectSchema.parse(valid)).not.toThrow()
       })
     })
     ```

2. **Backend Tests** (Vitest + Supertest)
   - Unit tests for repositories
   - Unit tests for services
   - Integration tests for API endpoints
   - Example:

     ```typescript
     describe('ProjectService', () => {
       it('creates project with valid data', async () => {
         const project = await projectService.create(userId, data)
         expect(project).toMatchObject(data)
       })
     })
     
     describe('POST /api/projects', () => {
       it('returns 201 with project data', async () => {
         const res = await request(app)
           .post('/api/projects')
           .set('Authorization', `Bearer ${token}`)
           .send({ name: 'Test' })
         expect(res.status).toBe(201)
       })
     })
     ```

3. **Frontend Tests** (Vitest + Testing Library)
   - Component tests
   - Composable tests
   - Router tests
   - Example:

     ```typescript
     describe('ProjectCard', () => {
       it('renders project name', () => {
         const { getByText } = render(ProjectCard, {
           props: { project: mockProject }
         })
         expect(getByText(mockProject.name)).toBeInTheDocument()
       })
     })
     ```

### Phase 5: Configuration & Tooling

1. **Root Package.json**

   ```json
   {
     "name": "xenix",
     "private": true,
     "scripts": {
       "dev": "pnpm run -r --parallel dev",
       "dev:app": "pnpm --filter @xenix/app dev",
       "dev:server": "pnpm --filter @xenix/server dev",
       "build": "pnpm run -r build",
       "test": "pnpm run -r test",
       "test:watch": "pnpm run -r test:watch",
       "lint": "eslint .",
       "format": "prettier --write .",
       "db:generate": "pnpm --filter @xenix/server db:generate",
       "db:migrate": "pnpm --filter @xenix/server db:migrate",
       "db:studio": "pnpm --filter @xenix/server db:studio"
     }
   }
   ```

2. **TypeScript Configuration**
   - Root `tsconfig.json` (base config)
   - Each package extends root config
   - Path aliases properly configured

3. **Environment Variables**

   ```env
   # Backend (.env)
   NODE_ENV=development
   PORT=3001
   DATABASE_URL=postgresql://user:pass@localhost:5432/xenix
   REDIS_URL=redis://localhost:6379
   JWT_SECRET=your-secret-key
   PYTHON_PATH=/path/to/python
   
   # Frontend (.env)
   VITE_API_URL=http://localhost:3001
   ```

4. **Docker Compose** (for PostgreSQL & Redis)

   ```yaml
   services:
     postgres:
       image: postgres:16
       ports:
         - "5432:5432"
       environment:
         POSTGRES_DB: xenix
         POSTGRES_USER: user
         POSTGRES_PASSWORD: pass
     
     redis:
       image: redis:7
       ports:
         - "6379:6379"
   ```

5. **Git Setup**
   - Update `.gitignore`:

     ```
     node_modules/
     dist/
     .env
     .env.local
     packages/*/dist
     packages/*/.nuxt
     .venv/
     __pycache__/
     *.pyc
     ```

### Phase 6: Migration Strategy

1. **Step 1: Setup Structure** (Day 1)
   - Create packages/ directory
   - Setup workspace configuration
   - Create shared package with initial schemas

2. **Step 2: Backend Migration** (Day 2-3)
   - Create server package
   - Setup Hono app with middleware
   - Migrate database schema (no changes, just move)
   - Create repositories for all entities
   - Create services with business logic
   - Migrate API routes one by one:
     - Start with auth (signin/signup)
     - Then projects, datasets, work-items
     - Finally ML endpoints (auto-tune, predict)
   - Setup BullMQ for background jobs
   - Test each endpoint as migrated

3. **Step 3: Frontend Migration** (Day 4-5)
   - Create app package
   - Setup Vite + Vue + Router
   - Setup Hono RPC client
   - Setup TanStack Query
   - Migrate pages one by one:
     - Start with signin/signup
     - Then dashboard/projects
     - Then work-items workflow
   - Migrate components (no API changes needed)
   - Setup auth store
   - Test entire user flow

4. **Step 4: Testing** (Day 6)
   - Write tests for critical paths
   - Test auth flow
   - Test ML workflow (upload → tune → predict)
   - Performance testing

5. **Step 5: Cleanup** (Day 7)
   - Delete old Nuxt files
   - Update documentation
   - Update README
   - Deploy testing

## Key Improvements from Current Architecture

### Type Safety

- ❌ Before: Manual type definitions, can drift
- ✅ After: Single source of truth (Zod schemas), end-to-end type safety

### API Layer

- ❌ Before: File-based routing, hard to trace, no validation
- ✅ After: Explicit routes, Zod validation, Hono RPC client

### Data Fetching

- ❌ Before: Manual `$fetch` calls, no caching, loading states
- ✅ After: TanStack Query with automatic caching, refetching, optimistic updates

### Architecture

- ❌ Before: Mixed concerns, direct DB access in handlers
- ✅ After: Clean layers (routes → services → repositories)

### Background Jobs

- ❌ Before: Database polling (inefficient)
- ✅ After: Redis-based queue (BullMQ)

### Error Handling

- ❌ Before: Inconsistent error responses
- ✅ After: Standardized error classes, proper HTTP status codes

### Testing

- ❌ Before: No tests
- ✅ After: Comprehensive test suite

### Developer Experience

- ❌ Before: Slow Nuxt builds, implicit routing
- ✅ After: Fast Vite HMR, explicit everything, auto-complete everywhere

## Breaking Changes

1. **API Base URL Change**
   - From: Nuxt's built-in `/api`
   - To: Explicit backend URL (e.g., `http://localhost:3001/api`)

2. **No Auto-Imports**
   - From: Nuxt auto-imports everything
   - To: Explicit imports (better for IDE support)

3. **Route Structure**
   - From: File-based pages auto-routing
   - To: Explicit route definitions in router config

4. **Environment Variables**
   - From: Nuxt's `useRuntimeConfig()`
   - To: Standard `import.meta.env.VITE_*`

## Risks & Mitigations

1. **Risk**: Large refactor, could introduce bugs
   - **Mitigation**: Migrate incrementally, test each step

2. **Risk**: Team needs to learn new patterns
   - **Mitigation**: Clear documentation, code examples

3. **Risk**: Python integration might break
   - **Mitigation**: Keep Python scripts unchanged, only improve executor

4. **Risk**: Database migrations during transition
   - **Mitigation**: No schema changes, only code changes
