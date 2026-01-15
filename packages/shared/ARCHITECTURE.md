# `@xenix/shared` Architecture

> Last updated at UTC+8 2026-01-15 13:10

## Overview

Package Purpose: Shared types, schemas, and constants across frontend and backend.

Single source of truth for type definitions and runtime validation. Exports TypeScript types and Zod schemas used by both frontend and backend.

## Structure

```
src/
├── index.ts           # Re-exports from schemas
├── schemas/           # Zod validation schemas
│   ├── index.ts
│   ├── user.ts        # User schema (signup, profile)
│   ├── project.ts     # Project CRUD schemas
│   ├── dataset.ts     # Dataset upload, list schemas
│   ├── task.ts        # Task query, delete schemas
│   ├── model.ts       # Model metadata schema
│   ├── predict.ts     # Prediction request/response schemas
│   └── __tests__/
├── types/             # TypeScript interfaces (if separate)
└── __tests__/
```

## Key Concepts

### Zod Schemas (Runtime Validation + Types)

Each schema provides:

1. **Runtime validation**: Used by backend `zValidator` middleware
2. **TypeScript type**: Extracted via `z.infer<typeof schema>`

Example:

```typescript
// schemas/project.ts
export const CreateProjectSchema = z.object({
  name: z.string().min(1).max(255),
  description: z.string().optional(),
});

export type CreateProjectDto = z.infer<typeof CreateProjectSchema>;

// Backend usage
.post("/", zValidator("json", CreateProjectSchema), async (c) => {
  const data = c.req.valid("json"); // Typed as CreateProjectDto
  // ...
})

// Frontend usage
import { CreateProjectSchema } from '@xenix/shared';
// Can validate client-side if needed
```

### Schema Organization

**User Schemas**:

- `UserSchema` - Base user type
- `SignupSchema` - Email, password, phone
- `SigninSchema` - Email/phone, password

**Project Schemas**:

- `CreateProjectSchema` - Name, description
- `UpdateProjectSchema` - Partial update
- `ProjectIdParamSchema` - Route param validation

**Dataset Schemas**:

- `UploadDatasetSchema` - Multipart upload
- `CreateDatasetSchema` - Metadata
- `DatasetIdParamSchema` - Route param

**Task Schemas**:

- `GetTasksQuerySchema` - Query: workItemId, type
- `TaskIdParamSchema` - Route param
- `DeleteFailedTasksQuerySchema` - Cleanup query

**Model Schemas**:

- `ModelMetadataSchema` - Model info
- `ModelParamsSchema` - Generic params

**Predict Schemas**:

- `CreatePredictionSchema` - Input + model params
- `PredictionResultSchema` - Output format

## Patterns

**Param Validation**

- Transform string to number for type-safe route params
- Zod schema definition for route parameters

**Query String Validation**

- Schema for query parameters with optional fields
- Enum values for fixed options (e.g., task types)

**JSON Body Validation**

- Schema for request body with constraints
- Optional and required fields
- Min/max constraints, string patterns

**Error Response Schema (Type)**

All errors follow:

```typescript
{
  code: string;      // 'NOT_FOUND', 'UNAUTHORIZED', 'VALIDATION_ERROR'
  error: string;     // Human-readable message
  details?: unknown; // Optional details (e.g., Zod field errors)
}
```

```

## HTTP Status Codes

- `200` - Success
- `201` - Created
- `202` - Accepted (async operation)
- `400` - Bad request (validation error)
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not found
- `409` - Conflict
- `500` - Internal server error

## Development

For development setup and commands, see [DEVELOPMENT.md](../../DEVELOPMENT.md).

Key note: Build shared first when dependencies change:
```bash
cd packages/shared && pnpm build
cd packages/backend && pnpm build:shared
```

## Usage

**Frontend**: Optional client-side validation or rely on backend validation errors

**Backend**:

- `zValidator` middleware auto-validates input
- `c.req.valid("json")` returns pre-validated, type-safe data

## Best Practices

✅ Keep schemas simple and focused
✅ Use enums for fixed values
✅ Add `.describe()` for documentation
✅ Extend schemas for reuse
✅ Export types via `z.infer<typeof schema>`
✅ Use schema transformations for data normalization

## Testing

```bash
pnpm test
```

Type definitions for schema validation:

```typescript
// Each schema exports type via z.infer
type CreateProjectDto = z.infer<typeof CreateProjectSchema>;
type TaskStatus = z.infer<typeof TaskSchema>['status'];
```
