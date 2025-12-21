import { pgTable, serial, text, varchar, timestamp, jsonb, integer, bigint } from 'drizzle-orm/pg-core';

export const tasks = pgTable('tasks', {
  id: serial('id').primaryKey(),
  taskId: varchar('task_id', { length: 255 }).notNull().unique(),
  type: varchar('type', { length: 50 }).notNull(), // 'tuning', 'comparison', 'prediction'
  status: varchar('status', { length: 50 }).notNull().default('pending'), // 'pending', 'running', 'completed', 'failed'
  model: varchar('model', { length: 100 }), // model name for tuning
  inputFile: text('input_file'),
  outputFile: text('output_file'),
  error: text('error'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});

export const modelResults = pgTable('model_results', {
  id: serial('id').primaryKey(),
  taskId: varchar('task_id', { length: 255 }).notNull(),
  model: varchar('model', { length: 100 }).notNull(),
  params: jsonb('params'), // best parameters from tuning
  mse_train: text('mse_train'),
  mae_train: text('mae_train'),
  r2_train: text('r2_train'),
  mse_test: text('mse_test'),
  mae_test: text('mae_test'),
  r2_test: text('r2_test'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
});

// Comparison results table removed - evaluation metrics from tuning are sufficient
// All model evaluation results are stored in modelResults table during hyperparameter tuning

// OpenTelemetry-compliant logs table
export const logs = pgTable('logs', {
  id: serial('id').primaryKey(),
  timestamp: bigint('timestamp', { mode: 'number' }).notNull(), // Unix timestamp in nanoseconds
  observedTimestamp: bigint('observed_timestamp', { mode: 'number' }).notNull(), // When log was observed
  traceId: varchar('trace_id', { length: 255 }).notNull(), // task_id as trace ID
  spanId: varchar('span_id', { length: 255 }), // Optional span ID
  severityText: varchar('severity_text', { length: 20 }).notNull(), // DEBUG, INFO, WARNING, ERROR, CRITICAL
  severityNumber: integer('severity_number').notNull(), // 1-24 per OpenTelemetry spec
  body: text('body').notNull(), // Log message
  resource: jsonb('resource'), // Resource attributes (e.g., service.name)
  attributes: jsonb('attributes'), // Additional attributes
  createdAt: timestamp('created_at').defaultNow().notNull(),
});
