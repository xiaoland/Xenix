# Frontend (packages/frontend) — Agent Context

## Tech Stack
- Vite + Vue 3 (`<script setup lang="ts">`)
- Pinia for state
- TanStack Query for server state
- Ant Design Vue UI
- UnoCSS for utilities + SCSS for complex layout
- i18n: no hard-coded user strings

## Directory Structure (Current)
```
src/
  api/            # API clients and request helpers
  components/     # shared UI components
  composables/    # Vue composables
  constants/      # shared constants
  i18n/           # locale resources
  layouts/        # layout components
  router/         # route definitions
  stores/         # Pinia stores
  utils/          # pure utilities
  views/          # route-level views
  App.vue
  main.ts
```

## Coding Conventions
- Use `<script setup lang="ts">` and Composition API.
- Fetch via TanStack Query composables (no direct API calls in components).
- Import shared types from `@xenix/shared`.
- Prefer UnoCSS utilities; use SCSS only for complex layout.
- User-facing text must go through i18n (`$t('key')`/`t('key')`).

## Current State
- Frontend contains legacy, redundant, and dead artifacts.
- Structure is partially feature-agnostic (views/router/stores split).
- Refactor target is a feature-first layout with strict documentation and cleanup.
