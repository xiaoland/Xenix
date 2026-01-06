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

## Schema Reference

### projects

Top-level container for organizing datasets and work items.

| Column      | Type      | Description                       |
| ----------- | --------- | --------------------------------- |
| id          | INTEGER   | Primary key                       |
| name        | TEXT      | Project name                      |
| description | TEXT      | Optional description              |
| status      | TEXT      | 'active', 'completed', 'archived' |
| createdAt   | TIMESTAMP | Creation time                     |
| updatedAt   | TIMESTAMP | Last update time                  |

### workItems

ML workflow session containing tasks.

| Column         | Type      | Description                       |
| -------------- | --------- | --------------------------------- |
| id             | INTEGER   | Primary key                       |
| projectId      | INTEGER   | FK to projects                    |
| name           | TEXT      | Work item name                    |
| description    | TEXT      | Optional description              |
| status         | TEXT      | 'active', 'completed', 'archived' |
| datasetId      | INTEGER   | Selected dataset ID               |
| featureColumns | JSON      | Selected feature columns array    |
| targetColumn   | TEXT      | Selected target column            |
| selectedModels | JSON      | Selected models array             |
| createdAt      | TIMESTAMP | Creation time                     |
| updatedAt      | TIMESTAMP | Last update time                  |

### datasets

Uploaded dataset files.

| Column      | Type      | Description               |
| ----------- | --------- | ------------------------- |
| id          | INTEGER   | Primary key               |
| projectId   | INTEGER   | FK to projects (optional) |
| name        | TEXT      | Dataset name              |
| description | TEXT      | Optional description      |
| filePath    | TEXT      | Path to file on disk      |
| fileName    | TEXT      | Original filename         |
| fileSize    | INTEGER   | File size in bytes        |
| columns     | JSON      | Column names array        |
| rowCount    | INTEGER   | Number of rows            |
| createdAt   | TIMESTAMP | Creation time             |
| updatedAt   | TIMESTAMP | Last update time          |

### tasks

ML operation tasks (tuning, prediction).

| Column     | Type      | Description                                 |
| ---------- | --------- | ------------------------------------------- |
| id         | INTEGER   | Primary key                                 |
| workItemId | INTEGER   | FK to workItems                             |
| type       | TEXT      | 'auto-tune', 'manual-tune', 'predict'       |
| parameter  | JSON      | Task input parameters                       |
| result     | JSON      | Task output (metrics, etc.)                 |
| status     | TEXT      | 'pending', 'running', 'completed', 'failed' |
| error      | TEXT      | Error message if failed                     |
| createdAt  | TIMESTAMP | Creation time                               |
| startedAt  | TIMESTAMP | Execution start time                        |
| endAt      | TIMESTAMP | Execution end time                          |

### modelMetadata

Available ML models and their parameter schemas.

| Column          | Type      | Description                          |
| --------------- | --------- | ------------------------------------ |
| id              | INTEGER   | Primary key                          |
| category        | TEXT      | 'regression', 'classification', etc. |
| name            | TEXT      | Unique model identifier              |
| label           | TEXT      | Human-readable name                  |
| paramSchema     | JSON      | JSON Schema for parameters           |
| paramGridSchema | JSON      | JSON Schema for grid search          |
| createdAt       | TIMESTAMP | Creation time                        |
| updatedAt       | TIMESTAMP | Last update time                     |

### logs

OpenTelemetry-compliant task execution logs.

| Column            | Type      | Description             |
| ----------------- | --------- | ----------------------- |
| id                | INTEGER   | Primary key             |
| timestamp         | INTEGER   | Log timestamp (ms)      |
| observedTimestamp | INTEGER   | When log was observed   |
| traceId           | TEXT      | Format: `task.{taskId}` |
| spanId            | TEXT      | Optional span ID        |
| severityText      | TEXT      | 'INFO', 'WARN', 'ERROR' |
| severityNumber    | INTEGER   | Numeric severity        |
| body              | TEXT      | Log message             |
| resource          | JSON      | Resource attributes     |
| attributes        | JSON      | Log attributes          |
| createdAt         | TIMESTAMP | Creation time           |

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
    type: 'auto-tune',
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

## JSON Columns

Several columns store JSON data:

- `tasks.parameter` - Task input parameters
- `tasks.result` - Task output (metrics, params)
- `workItems.featureColumns` - String array
- `workItems.selectedModels` - String array
- `datasets.columns` - Column names array
- `modelMetadata.paramSchema` - JSON Schema object

Access in TypeScript:

```typescript
const task = await db.select().from(schema.tasks).where(...);
const metrics = task[0].result?.metrics; // Typed as any
```
