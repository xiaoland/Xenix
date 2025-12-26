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

export const tasks = sqliteTable('tasks', {
  id: integer('id', { mode: 'number' }).primaryKey({ autoIncrement: true }),
  taskId: text('task_id').notNull().unique(),
  type: text('type').notNull(),
  status: text('status').notNull().default('pending'),
  model: text('model'),
  datasetId: text('dataset_id'),
  inputFile: text('input_file'),
  outputFile: text('output_file'),
  error: text('error'),
  progress: integer('progress'),  // Progress percentage (0-100)
  progressCurrent: integer('progress_current'),  // Current iteration
  progressTotal: integer('progress_total'),  // Total iterations
  progressMessage: text('progress_message'),  // Progress message
  createdAt: integer('created_at', { mode: 'timestamp' }).$defaultFn(() => new Date()).notNull(),
  updatedAt: integer('updated_at', { mode: 'timestamp' }).$defaultFn(() => new Date()).notNull(),
});

export const modelResults = sqliteTable('model_results', {
  id: integer('id', { mode: 'number' }).primaryKey({ autoIncrement: true }),
  taskId: text('task_id').notNull(),
  model: text('model').notNull(),
  params: text('params', { mode: 'json' }),
  mse_train: text('mse_train'),
  mae_train: text('mae_train'),
  r2_train: text('r2_train'),
  mse_test: text('mse_test'),
  mae_test: text('mae_test'),
  r2_test: text('r2_test'),
  createdAt: integer('created_at', { mode: 'timestamp' }).$defaultFn(() => new Date()).notNull(),
});

// OpenTelemetry-compliant logs table
export const logs = sqliteTable('logs', {
  id: integer('id', { mode: 'number' }).primaryKey({ autoIncrement: true }),
  timestamp: integer('timestamp', { mode: 'number' }).notNull(),
  observedTimestamp: integer('observed_timestamp', { mode: 'number' }).notNull(),
  traceId: text('trace_id').notNull(),
  spanId: text('span_id'),
  severityText: text('severity_text').notNull(),
  severityNumber: integer('severity_number').notNull(),
  body: text('body').notNull(),
  resource: text('resource', { mode: 'json' }),
  attributes: text('attributes', { mode: 'json' }),
  createdAt: integer('created_at', { mode: 'timestamp' }).$defaultFn(() => new Date()).notNull(),
});

