# Backend Architecture Module

## Purpose

Defines the organization, patterns, and conventions for the Xenix backend API.

## Key Concepts

### Hono Framework

- Lightweight, fast web framework
- Type-safe with TypeScript
- Middleware-based architecture

### RPC Pattern

Type-safe API calls between frontend and backend using Hono RPC:

```typescript
// Backend
const app = new Hono().basePath("/api");
const routes = app.get("/projects", async (c) => {
  const projects = await getProjects();
  return c.json({ projects });
});

// Frontend
const client = hc<typeof routes>("/api");
const res = await client.projects.$get();
```

### Middleware Stack

1. **CORS** - Cross-origin requests
2. **Auth** - JWT validation
3. **Logging** - Request/response logging
4. **Error Handling** - Global error responses

## Architecture Overview

```
packages/backend/
  src/
    index.ts          # App entry
    routes/           # API route definitions
    middleware/       # Custom middleware
    business/         # Business logic
      ml/             # ML-specific logic
    database/         # Drizzle ORM
      schema/         # Table definitions
      migrations/     # Database migrations
```

## Database Pattern

Using Drizzle ORM with PostgreSQL:

```typescript
// Schema definition
export const projects = pgTable("projects", {
  id: serial("id").primaryKey(),
  name: text("name").notNull(),
  createdAt: timestamp("created_at").defaultNow(),
});

// Query
const result = await db.select().from(projects);
```

## Error Handling

Standardized error responses:

```typescript
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": { ... }
}
```

## Related

- Backend code: `packages/backend/src/`
- Database: `packages/backend/src/database/`
- ML business logic: `packages/backend/src/business/ml/`
