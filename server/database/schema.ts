// Database schema that supports both PostgreSQL and SQLite
// The actual table builder is determined at runtime based on DATABASE_TYPE

import { pgTable, serial, text as pgText, varchar as pgVarchar, timestamp, jsonb, integer as pgInteger, bigint } from 'drizzle-orm/pg-core';
import { sqliteTable, text as sqliteText, integer as sqliteInteger } from 'drizzle-orm/sqlite-core';

const databaseType = process.env.DATABASE_TYPE || 
  (process.env.DATABASE_URL?.startsWith('sqlite') ? 'sqlite' : 'postgresql');

const isPostgres = databaseType === 'postgresql';

// For PostgreSQL
const pgDatasets = pgTable('datasets', {
  id: serial('id').primaryKey(),
  datasetId: pgVarchar('dataset_id', { length: 255 }).notNull().unique(),
  name: pgVarchar('name', { length: 255 }).notNull(),
  description: pgText('description'),
  filePath: pgText('file_path').notNull(),
  fileName: pgVarchar('file_name', { length: 255 }).notNull(),
  fileSize: bigint('file_size', { mode: 'number' }),
  columns: jsonb('columns'),
  rowCount: pgInteger('row_count'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});

const pgTasks = pgTable('tasks', {
  id: serial('id').primaryKey(),
  taskId: pgVarchar('task_id', { length: 255 }).notNull().unique(),
  type: pgVarchar('type', { length: 50 }).notNull(),
  status: pgVarchar('status', { length: 50 }).notNull().default('pending'),
  model: pgVarchar('model', { length: 100 }),
  datasetId: pgVarchar('dataset_id', { length: 255 }),
  inputFile: pgText('input_file'),
  outputFile: pgText('output_file'),
  error: pgText('error'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});

const pgModelResults = pgTable('model_results', {
  id: serial('id').primaryKey(),
  taskId: pgVarchar('task_id', { length: 255 }).notNull(),
  model: pgVarchar('model', { length: 100 }).notNull(),
  params: jsonb('params'),
  mse_train: pgText('mse_train'),
  mae_train: pgText('mae_train'),
  r2_train: pgText('r2_train'),
  mse_test: pgText('mse_test'),
  mae_test: pgText('mae_test'),
  r2_test: pgText('r2_test'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
});

const pgLogs = pgTable('logs', {
  id: serial('id').primaryKey(),
  timestamp: bigint('timestamp', { mode: 'number' }).notNull(),
  observedTimestamp: bigint('observed_timestamp', { mode: 'number' }).notNull(),
  traceId: pgVarchar('trace_id', { length: 255 }).notNull(),
  spanId: pgVarchar('span_id', { length: 255 }),
  severityText: pgVarchar('severity_text', { length: 20 }).notNull(),
  severityNumber: pgInteger('severity_number').notNull(),
  body: pgText('body').notNull(),
  resource: jsonb('resource'),
  attributes: jsonb('attributes'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
});

// For SQLite
const sqliteDatasets = sqliteTable('datasets', {
  id: sqliteInteger('id', { mode: 'number' }).primaryKey({ autoIncrement: true }),
  datasetId: sqliteText('dataset_id').notNull().unique(),
  name: sqliteText('name').notNull(),
  description: sqliteText('description'),
  filePath: sqliteText('file_path').notNull(),
  fileName: sqliteText('file_name').notNull(),
  fileSize: sqliteInteger('file_size', { mode: 'number' }),
  columns: sqliteText('columns', { mode: 'json' }),
  rowCount: sqliteInteger('row_count'),
  createdAt: sqliteInteger('created_at', { mode: 'timestamp' }).$defaultFn(() => new Date()).notNull(),
  updatedAt: sqliteInteger('updated_at', { mode: 'timestamp' }).$defaultFn(() => new Date()).notNull(),
});

const sqliteTasks = sqliteTable('tasks', {
  id: sqliteInteger('id', { mode: 'number' }).primaryKey({ autoIncrement: true }),
  taskId: sqliteText('task_id').notNull().unique(),
  type: sqliteText('type').notNull(),
  status: sqliteText('status').notNull().default('pending'),
  model: sqliteText('model'),
  datasetId: sqliteText('dataset_id'),
  inputFile: sqliteText('input_file'),
  outputFile: sqliteText('output_file'),
  error: sqliteText('error'),
  createdAt: sqliteInteger('created_at', { mode: 'timestamp' }).$defaultFn(() => new Date()).notNull(),
  updatedAt: sqliteInteger('updated_at', { mode: 'timestamp' }).$defaultFn(() => new Date()).notNull(),
});

const sqliteModelResults = sqliteTable('model_results', {
  id: sqliteInteger('id', { mode: 'number' }).primaryKey({ autoIncrement: true }),
  taskId: sqliteText('task_id').notNull(),
  model: sqliteText('model').notNull(),
  params: sqliteText('params', { mode: 'json' }),
  mse_train: sqliteText('mse_train'),
  mae_train: sqliteText('mae_train'),
  r2_train: sqliteText('r2_train'),
  mse_test: sqliteText('mse_test'),
  mae_test: sqliteText('mae_test'),
  r2_test: sqliteText('r2_test'),
  createdAt: sqliteInteger('created_at', { mode: 'timestamp' }).$defaultFn(() => new Date()).notNull(),
});

const sqliteLogs = sqliteTable('logs', {
  id: sqliteInteger('id', { mode: 'number' }).primaryKey({ autoIncrement: true }),
  timestamp: sqliteInteger('timestamp', { mode: 'number' }).notNull(),
  observedTimestamp: sqliteInteger('observed_timestamp', { mode: 'number' }).notNull(),
  traceId: sqliteText('trace_id').notNull(),
  spanId: sqliteText('span_id'),
  severityText: sqliteText('severity_text').notNull(),
  severityNumber: sqliteInteger('severity_number').notNull(),
  body: sqliteText('body').notNull(),
  resource: sqliteText('resource', { mode: 'json' }),
  attributes: sqliteText('attributes', { mode: 'json' }),
  createdAt: sqliteInteger('created_at', { mode: 'timestamp' }).$defaultFn(() => new Date()).notNull(),
});

// Export the appropriate schema based on database type
export const datasets = isPostgres ? pgDatasets : sqliteDatasets;
export const tasks = isPostgres ? pgTasks : sqliteTasks;
export const modelResults = isPostgres ? pgModelResults : sqliteModelResults;
export const logs = isPostgres ? pgLogs : sqliteLogs;
