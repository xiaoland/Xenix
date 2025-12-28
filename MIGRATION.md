# Database Migration Guide

## Applying the Schema Refactoring Migration

This guide explains how to apply the major database schema refactoring that consolidates the `tasks` and `model_results` tables.

### Prerequisites

1. **Backup your data** (if you have existing data)
   ```bash
   cp xenix.db xenix.db.backup
   ```

2. **Install dependencies** (if not already installed)
   ```bash
   pnpm install
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```

### Applying the Migration

#### Option 1: Using the migration script (Recommended)

Run the custom migration script:

```bash
node scripts/migrate.js
```

This script will:
- Create the database if it doesn't exist
- Track which migrations have been applied
- Apply migrations in order (0000, 0001, 0002)
- Show progress for each migration

#### Option 2: Manual SQL execution

If you prefer to apply the migration manually:

```bash
sqlite3 xenix.db < server/database/migrations/0002_complete_penance.sql
```

### What the Migration Does

The migration file `0002_complete_penance.sql` makes the following changes:

1. **Drops** the `model_results` table
2. **Removes** the `task_id` unique index from tasks
3. **Adds** new columns to tasks:
   - `parameter` (text/JSON)
   - `result` (text/JSON)
   - `started_at` (integer timestamp)
   - `end_at` (integer timestamp)
4. **Removes** old columns from tasks:
   - `task_id` (replaced by auto-increment `id`)
   - `model` (moved to `parameter.model`)
   - `dataset_id` (moved to `parameter.datasetId`)
   - `input_file` (replaced by `parameter.datasetId`)
   - `output_file` (moved to `result.outputFile` or `parameter.outputFile`)
   - `updated_at` (replaced by `started_at` and `end_at`)

### New Schema Structure

After migration, the `tasks` table will have:

```sql
CREATE TABLE tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,           -- 'auto-tune', 'train', 'predict'
  parameter TEXT,               -- JSON: { model, datasetId, featureColumns, ... }
  result TEXT,                  -- JSON: { params, metrics, outputFile, ... }
  status TEXT NOT NULL,         -- 'pending', 'running', 'completed', 'failed'
  error TEXT,
  created_at INTEGER NOT NULL,
  started_at INTEGER,
  end_at INTEGER
);
```

### Verifying the Migration

After applying the migration, verify it worked:

```bash
sqlite3 xenix.db ".schema tasks"
```

You should see the new column structure.

### Troubleshooting

**Error: "Cannot find package 'better-sqlite3'"**
- Run `pnpm install` to install dependencies first

**Error: "table model_results does not exist"**
- This is expected if you're running the migration on a fresh database
- The migration script will skip this error automatically

**Want to start fresh?**
```bash
rm xenix.db
node scripts/migrate.js
```

### Testing After Migration

1. Start the development server:
   ```bash
   pnpm run dev
   ```

2. Test the following workflows:
   - Upload a dataset
   - Run auto-tune (with ParamGrid editing)
   - Run manual train (with single parameter values)
   - View training history (expandable rows)
   - View logs for specific training runs
   - Run prediction with trained model
   - Download prediction results

### Rolling Back (Not Recommended)

If you need to roll back:
1. Restore from backup: `cp xenix.db.backup xenix.db`
2. Revert code changes to before commits 265ff6c

**Note**: There is no automated rollback migration. Manual SQL would be required to recreate the old schema.

## Migration Status

- ✅ Schema changes designed and generated
- ✅ Migration file created (0002_complete_penance.sql)
- ✅ Migration script created (scripts/migrate.js)
- ✅ Backend APIs updated to use new schema
- ✅ Frontend components updated to use new API structure
- ✅ Code refactored with composables for maintainability
- ⏳ Migration needs to be applied on your local environment
- ⏳ Full workflow testing after migration

## Support

If you encounter issues:
1. Check that all dependencies are installed
2. Verify .env file is configured correctly
3. Check the migration script output for specific error messages
4. Ensure you have write permissions to the database file location
