# Xenix Architecture

> Last updated at UTC+8 2026-01-15 13:08

## System Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                        Xenix ML Platform                           │
│                     (Monorepo: pnpm workspace)                     │
└────────────────────────────────────────────────────────────────────┘
     │                    │                     │                    │
     ▼                    ▼                     ▼                    ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Frontend   │  │   Backend    │  │   Shared     │  │  ML-Backend  │
│   (Vue 3)    │  │   (Hono)     │  │   (Types)    │  │  (Standalone)│
├──────────────┤  ├──────────────┤  ├──────────────┤  ├──────────────┤
│• Vite        │  │• REST API    │  │• Zod schemas │  │• Training    │
│• TanStack    │  │• PostgreSQL  │  │• TypeScript  │  │• Prediction  │
│  Query       │  │• DrizzleORM  │  │• Shared DTOs │  │• Python exec │
│• Pinia       │  │• JWT Auth    │  │• Error types │  │              │
│• Vue Router  │  │• ML Adapters │  │• Constants   │  │              │
│• Ant Design  │  │• File upload │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
     Port 5173        Port 3000
```

## Data Flow: ML Workflow

### 1. Prepare (Upload & Configure)

```
User Upload
  ↓
Frontend: POST /data/upload (multipart)
  ↓
Backend: Store file (local or OSS)
  ↓
Database: datasets record
  ↓
Frontend: Display columns (useDatasets hook)
```

### 2. Tune (Auto or Manual Training)

```
Frontend: Select features, target, model
  ↓
POST /train/batch-train or /train/manual-train
  ↓
Backend: Create task (status=pending)
  ↓
MLBackendAdapter selector:
  ├─ Development: SpawnAdapter (local Node.js process)
  └─ Production: AliyunFCAdapter (invoke FC function)
  ↓
ml-backend: Execute Python script
  ↓
Python: GridSearchCV or manual training
  ↓
Results: Write to DB + file storage
  ↓
Frontend: Poll useTasks (5s interval) → Display results
```

### 3. Predict (Batch Prediction)

```
Frontend: Submit new data
  ↓
POST /predict (with model params)
  ↓
Backend: Create predict task
  ↓
ML Backend: Load model → predict() → save CSV
  ↓
Frontend: Download via /download endpoint
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Vue 3 + Vite | SPA UI |
| **State** | Pinia + TanStack Query | App & server state |
| **API** | Hono RPC client | Type-safe communication |
| **Backend** | Hono + Node.js | REST API server |
| **Database** | PostgreSQL + DrizzleORM | Data persistence |
| **Auth** | JWT + localStorage | Authentication |
| **ML** | Python (scikit-learn, XGBoost, LightGBM) | Model training |
| **ML Execution** | Spawn / Aliyun FC | ML operation delivery |
| **Jobs** | BullMQ + Redis | Task queue (configured) |
| **File Storage** | Local / Aliyun OSS | Dataset & model storage |
| **UI** | Ant Design Vue + UnoCSS | Component library |
| **i18n** | vue-i18n | Internationalization |

## Package Structure

```
packages/
├── shared/              # Shared across all packages
│   ├── schemas/         # Zod validation schemas
│   ├── types/           # TypeScript type definitions
│   └── package.json     # @xenix/shared
│
├── frontend/            # Vue 3 SPA application
│   ├── src/
│   │   ├── main.ts      # App bootstrap
│   │   ├── api/         # Hono RPC client
│   │   ├── composables/ # Data fetching hooks (TanStack Query)
│   │   ├── stores/      # Pinia stores
│   │   ├── router/      # Vue Router config
│   │   ├── views/       # Page components
│   │   ├── components/  # Reusable components
│   │   └── styles/      # SCSS styles
│   └── package.json     # @xenix/frontend
│
├── backend/             # Hono REST API server
│   ├── src/
│   │   ├── index.ts     # App entry + routing
│   │   ├── config/      # Zod-validated config
│   │   ├── routes/      # Explicit route handlers
│   │   ├── middleware/  # Auth + error handling
│   │   ├── services/    # Business logic
│   │   ├── repositories/# Data access layer
│   │   ├── business/ml/ # ML operations abstraction
│   │   ├── adapters/    # ML execution adapters
│   │   ├── database/    # DrizzleORM schema
│   │   ├── errors/      # Custom error classes
│   │   ├── jobs/        # BullMQ job processors
│   │   ├── queues/      # Queue initialization
│   │   ├── storage/     # File handling
│   │   └── utils/       # Logger, utilities
│   └── package.json     # @xenix/backend
│
└── ml-backend/          # Standalone ML operations
    ├── src/
    │   ├── core/        # batch-train, single-train, predict
    │   ├── adapters/    # stdio, aliyun-fc I/O
    │   ├── types/       # Type definitions
    │   ├── utils/       # Python executor, logger
    │   └── python/      # Python scripts (side-by-side)
    └── package.json     # @xenix/ml-backend
```

## Architectural Patterns

**Frontend: Composable-Based Data Fetching**

- TanStack Query for caching, invalidation, polling
- Composables wrap all API calls
- Automatic refetch for long-running tasks

**Backend: Service → Repository → DB**

- Services contain business logic
- Repositories handle data access
- Direct instantiation (no DI container yet)

**ML Execution: Adapter Factory Pattern**

- Single adapter selected at startup
- SpawnAdapter: spawns local Node.js process
- AliyunFCAdapter: invokes FC function asynchronously

**Error Handling: Custom Hierarchy**

- Response format: `{code: string, error: string, details?: unknown}`
- Automatic Zod error handling
- Global error handler catches all exceptions

**Authentication: JWT + Context Injection**

- JWT verification + user lookup per request
- User stored in Hono context for route handlers

## Deployment

For comprehensive deployment information, see [DEPLOYMENT.md](./DEPLOYMENT.md):

- Development setup
- Production on Aliyun FC
- Database configuration
- CI/CD pipeline
- Monitoring and security

✅ **Monorepo (pnpm workspace)**: Shared types prevent drift, independent development, unified deployment
✅ **Hono Framework**: Lightweight, fast, composable middleware, type-safe routing
✅ **TanStack Query**: Automatic caching/invalidation, polling support, simple refetch logic
✅ **DrizzleORM**: Type-safe queries, migration support, PostgreSQL integration
✅ **ML Adapter Pattern**: Flexible execution (local/cloud), extensible, consistent interface

## Known Architectural Gaps

⚠️ **Dependency Injection**: Services instantiate repositories directly (consider DI container)
⚠️ **N+1 Queries**: Auth middleware does user lookup per request
⚠️ **Job Queue**: BullMQ configured but not actively integrated with routes
⚠️ **Fire-and-Forget**: ML tasks may not be properly tracked through job queue
⚠️ **Type Safety**: Some `any` types in auth store (frontend)
⚠️ **Token Refresh**: No automatic JWT refresh mechanism

## Testing Strategy

- **Vitest**: Unit tests configured for all packages
- **@vue/test-utils**: Vue component testing
- **Test files**: `__tests__/` folders in each package
- **Coverage**: Configured but not extensively documented

## Development Guidelines

See package-specific ARCHITECTURE.md files:

- [Frontend Architecture](packages/frontend/ARCHITECTURE.md)
- [Backend Architecture](packages/backend/ARCHITECTURE.md)
- [Shared Architecture](packages/shared/ARCHITECTURE.md)
- [ML Backend Architecture](packages/ml-backend/ARCHITECTURE.md)
