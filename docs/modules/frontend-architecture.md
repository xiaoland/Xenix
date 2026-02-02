# Frontend Architecture Module

## Purpose

Defines the organization, patterns, and conventions for the Xenix frontend codebase.

## Key Concepts

### Feature-Based Organization

Code is organized by feature rather than by technical layer:

```
features/
  auth/          # Everything related to authentication
  projects/      # Everything related to projects
  datasets/      # Everything related to datasets
  ...
```

Benefits:

- **Locality of Reasoning**: Everything for a feature is in one place
- **Clear Boundaries**: Features are self-contained
- **Easy Navigation**: Find what you need quickly

### State Management

**Server State** (TanStack Query):

- Data from API calls
- Cached and synchronized
- Automatic background updates

**Client State** (Pinia):

- UI state (modals, forms)
- User preferences
- Auth tokens

### Type Safety

- Hono RPC provides end-to-end type safety
- Shared types from `@xenix/shared`
- Feature-specific types in `features/<feature>/types/`

## Architecture Overview

```
src/
  features/     # Feature modules
  hooks/        # Shared composables
  services/     # API clients
  routes/       # Route definitions
  utils/        # Pure utilities
  constants/    # Shared constants
  i18n/         # Localization
  assets/       # Static assets
```

## API Pattern

All API calls go through the Hono RPC client:

```typescript
import { client } from "@/services/api-client";

const { data } = useQuery({
  queryKey: ["projects"],
  queryFn: async () => {
    const res = await client.projects.$get();
    if (!res.ok) throw new Error("Failed to fetch");
    return res.json();
  },
});
```

## Conventions

1. **Vue Components**: Use `<script setup lang="ts">`
2. **i18n**: No hard-coded strings, always use `$t('key')`
3. **Styling**: Prefer UnoCSS, SCSS for complex layouts
4. **Imports**: Use `@/` alias for all internal imports

## Related

- Feature docs: `docs/features/`
- Frontend code: `packages/frontend/src/`
- AGENTS.md: `packages/frontend/src/AGENTS.md`
