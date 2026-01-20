# Shared Package Development Guide

## Quick Start

### Setup

```bash
# From root directory
pnpm install

# No build step required - uses source dependencies pattern
# Backend and frontend consume TypeScript sources directly
```

## Overview

The shared package provides:

- **Zod Validation Schemas**: Runtime validation with type inference
- **TypeScript Types**: Type definitions for frontend and backend
- **Constants**: Shared application constants
- **DTOs**: Data Transfer Objects

## Structure

```
src/
├── schemas/         # Zod validation schemas
│   ├── auth.ts
│   ├── projects.ts
│   ├── datasets.ts
│   ├── tasks.ts
│   ├── models.ts
│   └── predict.ts
├── types/           # TypeScript type definitions
│   ├── index.ts
│   ├── auth.ts
│   ├── projects.ts
│   └── ...
└── constants.ts     # Application constants
```

## Development

### Source Dependencies Pattern

This package uses the **source dependencies** pattern - consuming packages import directly from TypeScript source files (not compiled output).

**Benefits:**

- Changes reflect immediately in backend/frontend without rebuild
- Faster development iteration
- Better IDE jump-to-definition experience
- Simpler mental model

**How it works:**

- `package.json` exports point to `./src/index.ts` (not `./dist/index.js`)
- Bundlers (tsup, Vite) handle TypeScript sources natively during their own builds
- This package is logically part of backend/frontend, just physically separated for organization

### Type Checking

```bash
# Type-check shared package
pnpm type-check

# Note: No build step needed for development
# Changes are immediately available to consumers
```

## Creating Validation Schemas

Use Zod for runtime validation:

```typescript
// src/schemas/projects.ts
import { z } from 'zod'

export const CreateProjectSchema = z.object({
  name: z.string().min(1, 'Project name is required'),
  description: z.string().optional(),
})

export const ProjectSchema = CreateProjectSchema.extend({
  id: z.string(),
  createdAt: z.date(),
  updatedAt: z.date(),
})

// Infer TypeScript type
export type Project = z.infer<typeof ProjectSchema>
export type CreateProjectInput = z.infer<typeof CreateProjectSchema>
```

## Using Schemas in Backend

```typescript
import { CreateProjectSchema, type CreateProjectInput } from '@xenix/shared'
import { zValidator } from '@hono/zod-validator'

app.post('/projects', 
  zValidator('json', CreateProjectSchema), 
  async (c) => {
    const data = c.req.valid('json') // Type-safe!
    // data has type CreateProjectInput
    return c.json(await projectService.create(data))
  }
)
```

## Using Types in Frontend

```typescript
import { type Project } from '@xenix/shared'

interface ProjectCardProps {
  project: Project
}

export const ProjectCard = defineComponent<ProjectCardProps>({
  // Component code
})
```

## Validation Patterns

### Parameter Validation

```typescript
export const UserIdSchema = z.object({
  id: z.string().uuid('Invalid user ID')
})
```

### Query String Validation

```typescript
export const ListQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(100).default(20),
  search: z.string().optional(),
  sort: z.enum(['asc', 'desc']).default('desc'),
})
```

### JSON Body Validation

```typescript
export const CreateDatasetSchema = z.object({
  name: z.string().min(1),
  description: z.string().optional(),
  file: z.instanceof(File),
})
```

## Error Response Schema

All API errors follow this format:

```typescript
export const ErrorResponseSchema = z.object({
  code: z.string(),
  error: z.string(),
  details: z.record(z.any()).optional(),
})

export type ErrorResponse = z.infer<typeof ErrorResponseSchema>
```

## Best Practices

✅ **Keep schemas focused**: One schema per entity or operation
✅ **Use meaningful error messages**: Help users understand validation failures
✅ **Export both schema and type**: Always do `z.infer<typeof MySchema>`
✅ **Document complex schemas**: Add comments explaining non-obvious validations
✅ **Reuse base schemas**: Extend from base schemas to avoid duplication

```typescript
// Good: Extend base schema
export const UpdateProjectSchema = ProjectSchema.extend({
  // Override specific fields
  name: z.string().optional(),
}).partial()

// Avoid: Duplicating fields
export const UpdateProjectSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  // ... duplicating fields from ProjectSchema
})
```

## Testing

```bash
pnpm test
pnpm test:watch
```

Test schemas validate correctly:

```typescript
import { describe, it, expect } from 'vitest'
import { CreateProjectSchema } from './projects'

describe('CreateProjectSchema', () => {
  it('validates valid input', () => {
    const result = CreateProjectSchema.safeParse({
      name: 'My Project',
    })
    expect(result.success).toBe(true)
  })

  it('rejects invalid input', () => {
    const result = CreateProjectSchema.safeParse({
      name: '', // Invalid: empty
    })
    expect(result.success).toBe(false)
  })
})
```

## Common Tasks

### Add New Schema

1. Create file in `src/schemas/`:

```typescript
// src/schemas/myEntity.ts
import { z } from 'zod'

export const MyEntitySchema = z.object({
  id: z.string(),
  name: z.string(),
})

export type MyEntity = z.infer<typeof MyEntitySchema>
```

1. Export from `src/schemas/index.ts`:

```typescript
export * from './myEntity'
```

1. Use in backend and frontend

### Update Existing Schema

```typescript
// Add new field
export const UpdatedSchema = ExistingSchema.extend({
  newField: z.string().optional(),
})
```

### Deprecate Schema

```typescript
/**
 * @deprecated Use NewSchema instead
 */
export const OldSchema = z.object({ /* ... */ })
```

## Build & Deployment

### Source Dependencies Workflow

With source dependencies, changes to `@xenix/shared` are immediately available:

```bash
# After editing src/schemas or src/types:

# 1. Save changes (no build needed)

# 2. Dev servers hot-reload automatically
# Backend: tsx watch picks up changes
# Frontend: Vite HMR picks up changes

# 3. For production builds, shared is bundled automatically
pnpm -F @xenix/backend build  # Bundles @xenix/shared from source
pnpm -F @xenix/frontend build # Bundles @xenix/shared from source
```

### Production Build Strategy

**Backend Build:**

- `@xenix/shared` is bundled into output from TypeScript source
- Other dependencies remain external (imported from `node_modules`)
- See [tsup.config.ts](../../backend/tsup.config.ts): `noExternal: ['@xenix/shared']`

**Frontend Build:**

- Vite bundles `@xenix/shared` TypeScript sources automatically
- No pre-compilation needed

**Important:** There is no separate build step for `@xenix/shared`. It's logically part of backend/frontend, just physically separated for code organization.

## Resources

- [Root DEVELOPMENT.md](../../DEVELOPMENT.md)
- [Shared Architecture](./ARCHITECTURE.md)
- [Zod Documentation](https://zod.dev/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
