# Frontend (packages/frontend) — Agent Context

## Tech Stack

- **Build Tool**: Vite 6.x
- **Framework**: Vue 3.5.x with `<script setup lang="ts">` and Composition API
- **State Management**:
  - Pinia 2.x for client state
  - TanStack Query (Vue Query) 5.x for server state
- **UI Library**: Ant Design Vue 4.x
- **Styling**: UnoCSS 66.x (utilities) + SCSS (complex layouts)
- **i18n**: vue-i18n 11.x (no hard-coded user strings)
- **HTTP Client**: Hono RPC client (type-safe, via `@xenix/backend`)
- **Testing**: Vitest 2.x with @vue/test-utils

## Directory Structure

```
src/
  app/              # App bootstrapping, global providers
  assets/           # Static assets
  constants/        # Shared constants
  features/         # Feature modules (see below)
  hooks/            # Shared composables
  i18n/             # Locale resources
  routes/           # Route definitions
  services/         # API clients, SDK wrappers
  styles/           # Global styles, CSS variables
  types/            # Local-only TypeScript types
  utils/            # Pure utilities
  App.vue
  main.ts
```

### Feature Folder Standard

Each feature is self-contained:

```
features/<feature>/
  api/              # Feature-specific API calls
  components/       # Feature-specific components
  pages/            # Route-level pages
  queries/          # TanStack Query hooks
  stores/           # Feature-specific Pinia stores
  types/            # Feature-specific types
  index.ts          # Public exports
```

## Features

1. **auth** - Authentication (signin/signup)
   - Pages: SignInView.vue, SignUpView.vue
   - Stores: auth.ts

2. **common** - Shared components
   - Components: DefaultLayout.vue, LanguageSwitcher.vue, MLBackendDeploymentSelector.vue, Steps.vue

3. **projects** - Project management (CRUD)
   - Pages: HomeView.vue
   - Components: ProjectCard.vue, ProjectFormModal.vue, WorkItemRow.vue
   - Queries: useProjects.ts

4. **work-items** - ML workflow items (Prepare → Tune → Predict)
   - Pages: WorkItemNewView.vue, WorkItemDetailView.vue
   - Queries: useWorkItems.ts

5. **datasets** - Dataset upload and management
   - Pages: DatasetsView.vue
   - Components: AddDataset.vue, DatasetSelector.vue, DatasetUpload.vue
   - Queries: useDatasets.ts

6. **tasks** - Background task monitoring
   - Pages: TasksView.vue
   - Queries: useTasks.ts

7. **ml** - ML-specific components
   - Components: PrepareStep.vue, TuningStep.vue, PredictionStep.vue, etc.
   - Queries: useModels.ts, useMLBackendDeployments.ts

## Coding Conventions

### Vue Components

- Use `<script setup lang="ts">` and Composition API exclusively
- Props/Emits must be typed with TypeScript interfaces
- Use `$t('key')` or `t('key')` from `useI18n()` for all user-facing text
- Prefer UnoCSS utilities; use SCSS only for complex layout

### Data Fetching

- **Never** call API directly from components
- Use TanStack Query composables from `features/<feature>/queries/`
- Query keys must be descriptive: `['projects']`, `['work-item', id]`, `['tasks', { workItemId, type }]`
- Handle loading/error states consistently

### API Pattern (Hono RPC)

```typescript
const { data, isLoading, error } = useQuery({
  queryKey: ["resource"],
  queryFn: async () => {
    const response = await client.resource.$get();
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Failed to fetch");
    }
    return response.json();
  },
});
```

### State Management

- Server state → TanStack Query
- Client state → Pinia stores in `features/<feature>/stores/`
- Never duplicate server state in Pinia

### Type Imports

- Shared types: `import type { X } from '@xenix/shared'`
- Local types: relative imports

### Import Patterns

```typescript
// Feature imports
import { useProjects } from "../projects/queries";
import { useAuthStore } from "../auth/stores";

// Shared imports
import { useFormatters } from "../../hooks";
import { DefaultLayout } from "../common";

// Service imports
import { client } from "../../services/api-client";
```

## Quick Reference

### Running Commands

```bash
# Development
pnpm run dev

# Build
pnpm run build

# Testing
pnpm run test
pnpm run test:coverage

# i18n
pnpm run i18n:check
```

### Key Files

- `src/main.ts` - App entry point
- `src/app/` - App bootstrapping and global context
- `src/routes/index.ts` - Route definitions
- `src/services/api-client.ts` - Hono RPC client
- `src/features/index.ts` - Features barrel export
- `src/hooks/index.ts` - Shared hooks
- `src/styles/index.ts` - Global styles entry
- `src/types/index.ts` - Local types entry

### Environment Variables

- `VITE_API_URL` - Backend API URL
- `VITE_LOCALE_BASE_URL` - i18n locale files base URL
