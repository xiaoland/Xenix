# Frontend Architecture

> **Package**: `@xenix/shared`
> **Framework**: Vue 3 + Vite
> **State**: Pinia + TanStack Query

## Overview

The frontend is a Single Page Application (SPA) built with Vue 3 (Composition API) and Vite. It follows modern patterns with composables for data fetching, Pinia for state management, and a type-safe Hono RPC client for API communication.

```
┌─────────────────────────────────┐
│     Vue 3 SPA (Vite)            │
├─────────────────────────────────┤
│  ┌──────────────────────────────┐
│  │   Vue Router (Explicit)      │
│  └──────────────────────────────┘
│           ↓
│  ┌──────────────────────────────┐
│  │   Views / Components         │
│  │   (Composition API)          │
│  └──────────────────────────────┘
│           ↓
│  ┌──────────────────────────────┐
│  │   Composables                │
│  │   (TanStack Query Hooks)     │
│  └──────────────────────────────┘
│           ↓
│  ┌──────────────────────────────┐
│  │   Hono RPC Client            │
│  │   (Type-Safe API)            │
│  └──────────────────────────────┘
│           ↓
│  ┌──────────────────────────────┐
│  │   Backend API                │
│  └──────────────────────────────┘
└─────────────────────────────────┘
```

## Directory Structure

```
src/
├── main.ts                  # App bootstrap
├── App.vue                  # Root component
├── vite-env.d.ts           # Vite type definitions
│
├── router/
│   └── index.ts            # Explicit route definitions (not file-based)
│
├── stores/
│   └── auth.ts             # Pinia auth store (token + user)
│
├── api/
│   └── client.ts           # Hono RPC client instance
│
├── composables/            # Data fetching hooks (TanStack Query)
│   ├── useProjects.ts      # useQuery + useMutation for projects
│   ├── useWorkItems.ts     # useQuery + useMutation for work items
│   ├── useDatasets.ts      # useQuery + useMutation for datasets
│   ├── useTasks.ts         # useQuery with polling for tasks
│   ├── useFormatters.ts    # Utility composables
│   └── index.ts            # Re-exports
│
├── components/             # Reusable Vue components
│   ├── common/             # Layout, common UI
│   ├── dataset/            # Dataset-related components
│   ├── ml/                 # ML operation components
│   └── project/            # Project-related components
│
├── views/                  # Page components (matched by router)
│   ├── HomeView.vue        # Dashboard
│   ├── auth/
│   │   ├── SignInView.vue
│   │   └── SignUpView.vue
│   ├── work-items/
│   │   ├── WorkItemNewView.vue
│   │   └── WorkItemDetailView.vue
│   ├── datasets/
│   │   └── DatasetsView.vue
│   └── tasks/
│       └── TasksView.vue
│
├── i18n/                   # Internationalization
│   ├── locales/            # Translation files (lazy-loaded)
│   └── index.ts            # i18n setup
│
├── constants/
│   ├── config.ts           # API URLs, polling config
│   └── ...
│
├── layouts/                # Layout components (if used)
│
├── styles/
│   ├── main.scss           # Global styles
│   └── variables.scss      # SCSS variables
│
└── __tests__/              # Unit tests
```

## Key Patterns

**Data Fetching with TanStack Query**

- Query pattern: useQuery for read-only data
- Mutation pattern: useMutation for create/update/delete with query invalidation
- Polling pattern: refetchInterval for long-running tasks (e.g., 5s for ML operations)
- Benefits: Automatic caching, background refetch, polling, invalidation, loading/error states

**API Client (Hono RPC)**

- Type-safe client using Hono's `hc` function
- Imports backend's `AppType` for end-to-end type safety
- Authorization headers automatically injected from localStorage
- Benefits: Auto-completion from backend, type inference, consistent error handling

**Route Definitions (Explicit)**

- Route definitions in `router/index.ts` (not file-based)
- Meta fields for access control (e.g., `requiresAuth: true`)
- Navigation guard checks authentication before route access
- ✅ Response typing inferred from backend

**Usage**:

```typescript
// Type inference: response is typed based on backend route
const response = await client.projects[':id'].$get({
  param: { id: '123' },
});

// Can also use mutations
await client.projects.$post({ json: { name: 'New' } });
```

### 3. Route Definitions (Explicit)

```typescript
// router/index.ts
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/HomeView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/auth/signin',
    name: 'SignIn',
    component: () => import('../views/auth/SignInView.vue'),
  },
  {
    path: '/work-items/:id',
    name: 'WorkItemDetail',
    component: () => import('../views/work-items/WorkItemDetailView.vue'),
    meta: { requiresAuth: true },
  },
];

// Auth guard
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('auth_token');
  if (to.meta.requiresAuth && !token) {
    next('/auth/signin');
  } else {
    next();
  }
});
```

**Pinia Store (Auth)**

- Token and user stored in ref state
- Initialized from localStorage on app load
- login/signup/logout methods for auth flow
- Computed property `isAuthenticated` for access checks

**Component Pattern (Composition API)**

- `<script setup>` with TypeScript
- Reactive state: `ref()` for primitives, `computed()` for derived state
- Composables imported for data fetching and utilities
- Template access to reactive data and methods
- Navigation via `useRouter()`, i18n via `useI18n()`

## Authentication Flow

```
User Input
  ↓
POST /auth/signin (credentials)
  ↓
Backend verifies + returns JWT
  ↓
Frontend: Store token in localStorage
  ↓
Hono Client: Inject Authorization header in all requests
  ↓
Backend Middleware: Verify JWT
  ↓
Route handler receives authenticated user
```

## Build & Deployment

### Development

```bash
pnpm dev:frontend
# Starts Vite dev server on http://localhost:5173
# Hot Module Replacement enabled
# Import paths: @/ = src/
```

### Production Build

```bash
pnpm build:frontend
# Outputs to dist/
# Ready for deployment to CDN or static hosting
```

### Environment Variables

```
VITE_API_URL=http://localhost:3000  # Backend API URL
```

## Styling

**UnoCSS** (utility-first CSS framework):

- Configured in `uno.config.ts`
- Import with `import 'uno.css'`
- Use utility classes in templates

**SCSS** (complex styles):

- Global styles in `styles/main.scss`
- Component scoped styles: `<style scoped lang="scss">`

**Ant Design Vue**:

- Component library for UI elements
- Imported in main.ts
- Global styles with `import 'ant-design-vue/dist/reset.css'`

## i18n (Internationalization)

- Locale files lazy-loaded from `public/locales/`
- useI18n composable for accessing translation function `t(key)`
- Locale switching via i18n instance

## Testing

**Vitest** + **@vue/test-utils**:

```typescript
// src/__tests__/components/ProjectCard.spec.ts
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import ProjectCard from '@/components/ProjectCard.vue';

describe('ProjectCard', () => {
  it('renders project name', () => {
    const wrapper = mount(ProjectCard, {
      props: { project: { id: 1, name: 'Test' } }
    });
    expect(wrapper.text()).toContain('Test');
  });
});
```

## Development Guidelines

For comprehensive development guide including setup, conventions, and testing, see [DEVELOPMENT.md](../../DEVELOPMENT.md).

### Naming Conventions

- **Files**: kebab-case (useProjects.ts, ProjectCard.vue)
- **Components**: PascalCase (ProjectCard, WorkItemForm)
- **Composables**: camelCase starting with "use" (useProjects, useFormatters)
- **Stores**: descriptive names (auth, projects)

### Imports

- ✅ Use alias: `import { ... } from '@/composables'` (@ = src/)
- ✅ Group imports: vue, external, then local
- ✅ Explicit imports (avoid * imports)

### Reactivity

- ✅ Use `ref()` for primitive values
- ✅ Use `computed()` for derived state
- ✅ Use `reactive()` for object state (less common)
- ✅ Use TanStack Query for server state

### Error Handling

- ✅ Check `response.ok` before parsing
- ✅ Throw errors from composables
- ✅ Catch in component handlers
- ✅ Display user-friendly messages

## Known Issues & TODOs

⚠️ **Auth Token Duplication**: Pinia store + localStorage duplication (consider single source of truth)
⚠️ **No Token Refresh**: JWT token might expire without refresh mechanism
⚠️ **Type Safety**: Some `any` types in auth store (user object)
⚠️ **Legacy Services**: `src/services/` folder mentioned as "being phased out"

## Related Documentation

- [Root Architecture](../../ARCHITECTURE.md)
- [Backend Architecture](../backend/ARCHITECTURE.md)
- [Shared Architecture](../shared/ARCHITECTURE.md)
