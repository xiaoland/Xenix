# ADR-003: Hono RPC for Type-Safe APIs

## Status

Accepted

## Context

Traditional REST APIs require manual type definitions on both frontend and backend, leading to:

- Type drift between frontend and backend
- Runtime errors from mismatched types
- Extra maintenance for type definitions
- No autocomplete for API endpoints

## Decision

Use **Hono RPC** for type-safe API communication between frontend and backend:

```typescript
// Backend
const app = new Hono().basePath("/api");
const routes = app.get("/projects", async (c) => {
  return c.json({ projects: await getProjects() });
});

// Frontend
const client = hc<typeof routes>("/api");
const res = await client.projects.$get();
const data = await res.json(); // Fully typed!
```

## Consequences

**Positive**:

- End-to-end type safety
- Autocomplete for API endpoints
- Single source of truth for types
- Compile-time error detection

**Negative**:

- Tight coupling between frontend and backend (acceptable for monorepo)
- Requires both to be TypeScript

## Related

- Hono docs: https://hono.dev/docs/guides/rpc
- Backend code: `packages/backend/src/routes/`
- Frontend code: `packages/frontend/src/services/api-client.ts`
