// SQLite database schema for Xenix

import { sqliteTable, text, integer } from 'drizzle-orm/sqlite-core';

// Model metadata table for storing model information and ParamGrid schemas
export const modelMetadata = sqliteTable('model_metadata', {
  id: integer('id', { mode: 'number' }).primaryKey({ autoIncrement: true }),
  category: text('category').notNull(), // e.g., 'regression', 'classification'
  name: text('name').notNull().unique(), // e.g., 'regression.adaboost'
  label: text('label').notNull(), // Human-readable name, e.g., 'AdaBoost'
  paramGridSchema: text('param_grid_schema', { mode: 'json' }), // JSON schema from pydantic model
  createdAt: integer('created_at', { mode: 'timestamp' }).$defaultFn(() => new Date()).notNull(),
  updatedAt: integer('updated_at', { mode: 'timestamp' }).$defaultFn(() => new Date()).notNull(),
});

// Datasets table for data manager - stores uploaded data files for reuse
export const datasets = sqliteTable('datasets', {
  id: integer('id', { mode: 'number' }).primaryKey({ autoIncrement: true }),
  datasetId: text('dataset_id').notNull().unique(),
  name: text('name').notNull(),
  description: text('description'),
  filePath: text('file_path').notNull(),
  fileName: text('file_name').notNull(),
  fileSize: integer('file_size', { mode: 'number' }),
  columns: text('columns', { mode: 'json' }),
  rowCount: integer('row_count'),
  createdAt: integer('created_at', { mode: 'timestamp' }).$defaultFn(() => new Date()).notNull(),
  updatedAt: integer('updated_at', { mode: 'timestamp' }).$defaultFn(() => new Date()).notNull(),
});

// Consolidated tasks table
// Type values: 'auto-tune', 'train', 'predict'
export const tasks = sqliteTable('tasks', {
  id: integer('id', { mode: 'number' }).primaryKey({ autoIncrement: true }),
  type: text('type').notNull(), // 'auto-tune', 'train', 'predict'
  parameter: text('parameter', { mode: 'json' }), // Task parameters as JSON object
  result: text('result', { mode: 'json' }), // Task results/metrics as JSON object
  status: text('status').notNull().default('pending'),
  error: text('error'),
  createdAt: integer('created_at', { mode: 'timestamp' }).$defaultFn(() => new Date()).notNull(),
  startedAt: integer('started_at', { mode: 'timestamp' }),
  endAt: integer('end_at', { mode: 'timestamp' }),
});

// OpenTelemetry-compliant logs table
// trace_id format: task.{task.id} for task-related logs
export const logs = sqliteTable('logs', {
  id: integer('id', { mode: 'number' }).primaryKey({ autoIncrement: true }),
  timestamp: integer('timestamp', { mode: 'number' }).notNull(),
  observedTimestamp: integer('observed_timestamp', { mode: 'number' }).notNull(),
  traceId: text('trace_id').notNull(), // Format: task.{task.id}
  spanId: text('span_id'),
  severityText: text('severity_text').notNull(),
  severityNumber: integer('severity_number').notNull(),
  body: text('body').notNull(),
  resource: text('resource', { mode: 'json' }),
  attributes: text('attributes', { mode: 'json' }),
  createdAt: integer('created_at', { mode: 'timestamp' }).$defaultFn(() => new Date()).notNull(),
});

