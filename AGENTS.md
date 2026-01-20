# Xenix

Ship a easy-to-use, out-of-box ML workflow platform with separate frontend/backend stacks and shared schemas.

## Primary areas (load on need)

- packages/frontend – Vite + Vue 3 Composition API; Pinia + TanStack Query; Ant Design Vue UI; UnoCSS/SCSS styling.
- packages/backend – Hono app, Drizzle/PostgreSQL, middleware + business logic folders, Python executor integration under `business/ml`.
- packages/shared – shared TypeScript types and Zod schemas that keep both stacks in sync.
- packages/ml-backend – Python-heavy model training helpers; check `ml-backend` folder for scripts and dependencies managed with pdm.
- data/ + datasets/ + uploads/ – configuration parameters and runtime artifacts; avoid committing large blobs.

## Workflow hooks

- Prepare → Tune → Predict; dataset upload, column selection, tuning task queue, prediction task queue.
- Supported regression families: linear, polynomial, KNN, trees, ensembles (AdaBoost/GBDT/RF), XGBoost, LightGBM, Bayesian ridge.
- Background tasks live in the backend routes and are typically triggered through TanStack Query mutations.

## Quick commands

- pnpm run db:generate → Drizzle migrations, pnpm run db:migrate applies them.
- pnpm install / pnpm run dev from workspace root to bring up frontend + backend (Hono) while Python agents use `pdm install` inside `packages/ml-backend`.
- Use `pythonExecutor.ts` for any Python <> Node orchestrations; keep JSON I/O contracts stable.

## Documents to open when context is needed

- Architecture: [docs/structure.md](docs/structure.md) and [docs/ARCHITECTURE_INDEX.md](docs/ARCHITECTURE_INDEX.md).
- Deployment plan: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) and [docs/deployment/index.md](docs/deployment/index.md).
- Development/usage references: [docs/development.md](docs/development.md) and [docs/usage.md](docs/usage.md).
- Coding plans (monorepo refactor, tuning UX, Aliyun FC) under [docs/coding-plan](docs/coding-plan).

## Guiding rules for agents

- Vue components use `<script setup lang="ts">` and Composition API; fetch logic through TanStack Query composables (useProjects, useWorkItems, etc.).
- Hono routes are explicit files; runtime validation should align with `packages/shared` Zod schemas.
- Avoid hard-encoded user-facing text, use i18n instead ( `$t('key')`/`t('key')` ).
- Prefer UnoCSS utilities, reserve SCSS for complex layout.
- Type imports should come from `@xenix/shared`; prefer TypeScript-first edits and keep linting from ESLint config up to date.# AGENTS.md for `Xenix`
