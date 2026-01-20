# Database Directory

DrizzleORM with SQLite database configuration and schema.

## Overview

- **ORM:** DrizzleORM
- **Database:** SQLite
- **Schema:** `schema.ts`
- **Migrations:** `migrations/` folder

## Files

### index.ts

Database client initialization:

```typescript
import Database from 'better-sqlite3';
import { drizzle } from 'drizzle-orm/better-sqlite3';

const sqlite = new Database('./data.db');
export const db = drizzle(sqlite);
```

### schema.ts

Database table definitions.

## Usage Examples

### Query

```typescript
import { and, eq } from 'drizzle-orm';
import { db } from '~/server/database';
import * as schema from '~/server/database/schema';

// Select all projects
const projects = await db.select().from(schema.projects);

// Select with condition
const task = await db
  .select()
  .from(schema.tasks)
  .where(eq(schema.tasks.id, taskId));

// Join work items with tasks
const workItem = await db
  .select()
  .from(schema.workItems)
  .where(eq(schema.workItems.id, id));
```

### Insert

```typescript
const [newTask] = await db
  .insert(schema.tasks)
  .values({
    workItemId: workItemId,
    type: 'batch-train',
    parameter: { model, datasetId, featureColumns, targetColumn },
    status: 'pending',
  })
  .returning();
```

### Update

```typescript
await db
  .update(schema.tasks)
  .set({
    status: 'completed',
    result: { metrics: { r2: 0.95 } },
    endAt: new Date(),
  })
  .where(eq(schema.tasks.id, taskId));
```

### Delete

```typescript
await db
  .delete(schema.tasks)
  .where(
    and(
      eq(schema.tasks.workItemId, workItemId),
      eq(schema.tasks.status, 'failed')
    )
  );
```

## Migrations

### Generate Migration

```bash
pnpm run db:generate
```

### Apply Migration

```bash
pnpm run db:migrate
```
