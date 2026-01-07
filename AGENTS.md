# AGENTS.md for `Xenix`

Xenix is a Machine Learning Model Training and Prediction Platform that provides an interface for teachers and mid-small enterprises to analyze their data with ease.

## Tech Stacks

- **Frontend Framework:** Vite + Vue 3 (Composition API)
- **Backend Framework:** Hono (Node.js server)
- **UI Library:** Ant Design Vue
- **Style management:** UnoCSS (icons and simple styles) + SCSS (complex styles)
- **Database:** DrizzleORM + PostgreSQL
- **State Management:** Pinia + TanStack Query (Vue Query)
- **Automation testing:** Vitest (with `@vue/test-utils`)
- **ML Backend:** Python (scikit-learn, XGBoost, LightGBM)
- **Package management:** pnpm (monorepo workspace), pdm (Python)

## Core Workflow

The application follows a 3-step ML workflow:

1. **Prepare** - Upload dataset, select feature columns and target column
2. **Tune** - Train models with auto/manual hyperparameter tuning
3. **Predict** - Use trained model for batch predictions

## Project Structure (Monorepo)

```bash
Xenix/
├── packages/
│   ├── shared/              # Shared TypeScript types & Zod schemas
│   │   ├── src/
│   │   │   ├── schemas/     # Zod validation schemas
│   │   │   └── types/       # Shared TypeScript types
│   │   └── package.json
│   │
│   ├── frontend/            # Frontend application (Vite + Vue 3)
│   │   ├── src/
│   │   │   ├── main.ts
│   │   │   ├── App.vue
│   │   │   ├── components/  # Vue components (Composition API)
│   │   │   ├── views/       # Page components
│   │   │   ├── router/      # Vue Router config (explicit routing)
│   │   │   ├── stores/      # Pinia stores (auth, global state)
│   │   │   ├── composables/ # TanStack Query composables
│   │   │   ├── api/         # Hono RPC client
│   │   │   ├── services/    # Legacy services (being phased out)
│   │   │   ├── styles/      # SCSS styles
│   │   │   └── locales/     # i18n translations
│   │   ├── vite.config.ts
│   │   └── package.json
│   │
│   └── backend/             # Backend API (Hono server)
│       ├── src/
│       │   ├── index.ts     # Hono app entry (exports AppType)
│       │   ├── routes/      # API routes (explicit, grouped)
│       │   ├── middleware/  # Auth, CORS, logging
│       │   ├── business/ml/ # ML business logic & Python scripts
│       │   │   └── regression/ # Regression model implementations
│       │   ├── database/    # Drizzle schema & migrations
│       │   └── utils/       # Server utilities
│       └── package.json
│
├── docs/                    # Documentation
│   ├── plan/                # Plan-specific documentation
│   │   ├── monorepo-refactor-vite-vue-hono.md
│   │   └── frontend-modernization.md
│   ├── MONOREPO_STATUS.md   # Current status analysis
│   └── TODO.md              # Quick reference checklist
├── datasets/                # Uploaded dataset storage
├── uploads/                 # User file uploads
├── data/                    # Model parameters & configuration
├── pnpm-workspace.yaml      # pnpm monorepo configuration
└── docker-compose.yml       # PostgreSQL + Redis services
```

## Key Concepts

### Work Items

A work item represents a complete ML workflow session, containing:

- Dataset reference
- Selected feature/target columns
- Tuning tasks (auto/manual)
- Selected models for prediction

### Tasks

Background tasks for ML operations:

- `auto-tune` - GridSearchCV hyperparameter tuning
- `manual-tune` - Manual parameter configuration
- `predict` - Batch prediction execution

### Supported Models (Regression)

- Linear Regression, Ridge, Lasso
- Polynomial Regression
- K-Nearest Neighbors
- Decision Tree, Random Forest
- AdaBoost, GBDT
- XGBoost, LightGBM
- Bayesian Ridge Regression

## Development

- `.env`
- Run `pnpm run db:generate` to generate migrations
- Run `pnpm run db:migrate` to apply the migrations

## Coding Guidelines

1. **Vue Components:** Use `<script setup lang="ts">` with Composition API
2. **Data Fetching:** Use TanStack Query composables (useProjects, useWorkItems, etc.)
3. **API Endpoints:** Follow Hono explicit routing (`routes/projects.ts`, `routes/auth.ts`)
4. **Database:** Use DrizzleORM with PostgreSQL, define schema in `packages/backend/src/database/schema.ts`
5. **Python Integration:** Execute via `pythonExecutor.ts`, use JSON for I/O
6. **i18n:** All user-facing strings should use `$t('key')` or `t('key')`
7. **Styling:** Prefer UnoCSS utility classes, use SCSS for complex styles
8. **Type Safety:** Import types from `@xenix/shared` package

## Modern Patterns (Implemented)

### Frontend

- **TanStack Query (Vue Query):** All data fetching uses composables with automatic caching
  - Example: `useProjects()`, `useWorkItems()`, `useDatasets()`
  - Benefits: Automatic cache invalidation, background refetching, loading states
- **Composables Architecture:** Reusable business logic in `src/composables/`
  - Query hooks: `useQuery` for fetching data
  - Mutation hooks: `useMutation` for create/update/delete operations
  - Utility hooks: `useFormatters` for formatting utilities

- **Hono RPC Client:** Type-safe API client (setup ready, optional migration)
  - Backend exports `AppType` for end-to-end type safety
  - Client in `src/api/client.ts`

- **Explicit Routing:** Vue Router with explicit route definitions (no file-based routing)

### Backend

- **Hono Framework:** Fast, lightweight server with middleware stack
- **Zod Schemas:** Runtime validation schemas in `@xenix/shared` (available but not yet applied to routes)
- **PostgreSQL:** Production-ready database with DrizzleORM
- **Redis Ready:** Configured for future job queue implementation (BullMQ)

### Shared

- **Monorepo:** pnpm workspace with shared types and schemas
- **Type Safety:** Full TypeScript coverage across frontend and backend
- **Zod Schemas:** Runtime validation + TypeScript types from single source
