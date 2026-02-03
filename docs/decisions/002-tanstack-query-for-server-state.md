# ADR-002: TanStack Query for Server State

## Status

Accepted

## Context

The frontend needed a robust solution for managing server state (data from API calls). Previous approaches using Pinia for everything led to:

- Manual caching logic
- Duplicate state between Pinia and components
- Complex synchronization code
- No automatic background updates

## Decision

Use **TanStack Query (Vue Query)** for all server state management:

```typescript
const { data, isLoading, error } = useQuery({
  queryKey: ["projects"],
  queryFn: fetchProjects,
});
```

Pinia is reserved for client state only (UI state, auth tokens, user preferences).

## Consequences

**Positive**:

- Automatic caching and background updates
- Built-in loading and error states
- Optimistic updates support
- DevTools for debugging
- Reduced boilerplate code

**Negative**:

- Learning curve for developers new to TanStack Query
- Additional dependency

## Guidelines

1. **Always** use TanStack Query for API calls
2. **Never** call APIs directly from components
3. Query keys must be descriptive: `['projects']`, `['work-item', id]`
4. Handle loading/error states consistently

## Related

- TanStack Query docs: https://tanstack.com/query/latest
- Frontend code: `packages/frontend/src/features/*/queries/`
