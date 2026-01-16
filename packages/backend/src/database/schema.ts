// PostgreSQL database schema for Xenix
import {
  boolean,
  index,
  integer,
  jsonb,
  pgTable,
  serial,
  text,
  timestamp,
  uuid,
} from 'drizzle-orm/pg-core';

// Users table for authentication and user management
export const users = pgTable('users', {
  id: uuid('id').defaultRandom().primaryKey(),
  email: text('email').notNull().unique(),
  phone: text('phone'),
  password: text('password').notNull(),
  createdAt: timestamp('created_at', { mode: 'date' })
    .$defaultFn(() => new Date())
    .notNull(),
  updatedAt: timestamp('updated_at', { mode: 'date' })
    .$defaultFn(() => new Date())
    .notNull(),
});

// Model metadata table for storing model information and ModelParam schemas
export const modelMetadata = pgTable('model_metadata', {
  id: serial('id').primaryKey(),
  category: text('category').notNull(), // e.g., 'regression', 'classification'
  name: text('name').notNull().unique(), // e.g., 'regression.adaboost'
  label: text('label').notNull(), // Human-readable name, e.g., 'AdaBoost'
  paramSchema: jsonb('param_schema'), // JSON schema from pydantic model
  paramGridSchema: jsonb('param_grid_schema'), // JSON schema for parameter grid
  createdAt: timestamp('created_at', { mode: 'date' })
    .$defaultFn(() => new Date())
    .notNull(),
  updatedAt: timestamp('updated_at', { mode: 'date' })
    .$defaultFn(() => new Date())
    .notNull(),
});

// Datasets table for data manager - stores uploaded data files for reuse
export const datasets = pgTable('datasets', {
  id: serial('id').primaryKey(),
  projectId: integer('project_id'), // Reference to project
  name: text('name').notNull(),
  description: text('description'),
  filePath: text('file_path').notNull(),
  fileName: text('file_name').notNull(),
  fileSize: integer('file_size'),
  columns: jsonb('columns'),
  rowCount: integer('row_count'),
  createdAt: timestamp('created_at', { mode: 'date' })
    .$defaultFn(() => new Date())
    .notNull(),
  updatedAt: timestamp('updated_at', { mode: 'date' })
    .$defaultFn(() => new Date())
    .notNull(),
});

// ML Backend Workers table - tracks available ML backend execution environments
export const mlBackendWorkers = pgTable(
  'ml_backend_workers',
  {
    id: serial('id').primaryKey(),
    name: text('name').notNull().unique(),
    createdBy: uuid('created_by').references(() => users.id),
    adapter: text('adapter').notNull(), // 'aliyun-fc' | 'spawn'
    adapterParams: jsonb('adapter_params').notNull().default({}),
    isDefault: boolean('is_default').notNull().default(false),
    isActive: boolean('is_active').notNull().default(true),
    createdAt: timestamp('created_at', { mode: 'date' })
      .$defaultFn(() => new Date())
      .notNull(),
    updatedAt: timestamp('updated_at', { mode: 'date' })
      .$defaultFn(() => new Date())
      .notNull(),
  },
  (table) => ({
    adapterIdx: index('idx_ml_backend_workers_adapter').on(table.adapter),
    defaultIdx: index('idx_ml_backend_workers_default').on(table.isDefault),
  }),
);

// Consolidated tasks table
// Type values: 'batch-train', 'single-train', 'predict'
export const tasks = pgTable(
  'tasks',
  {
    id: serial('id').primaryKey(),
    workItemId: integer('work_item_id'), // Reference to work item
    mlBackendWorkerId: integer('ml_backend_worker_id').references(
      () => mlBackendWorkers.id,
    ), // Reference to ML backend worker
    type: text('type').notNull(), // 'batch-train', 'single-train', 'predict'
    parameter: jsonb('parameter'), // Task parameters as JSON object
    result: jsonb('result'), // Task results/metrics as JSON object
    status: text('status').notNull().default('pending'),
    error: text('error'),
    createdAt: timestamp('created_at', { mode: 'date' })
      .$defaultFn(() => new Date())
      .notNull(),
    startedAt: timestamp('started_at', { mode: 'date' }),
    endAt: timestamp('end_at', { mode: 'date' }),
  },
  (table) => ({
    workerIdx: index('idx_tasks_worker').on(table.mlBackendWorkerId),
  }),
);

// OpenTelemetry-compliant logs table
// trace_id format: task.{task.id} for task-related logs
export const logs = pgTable('logs', {
  id: serial('id').primaryKey(),
  timestamp: integer('timestamp').notNull(),
  observedTimestamp: integer('observed_timestamp').notNull(),
  traceId: text('trace_id').notNull(), // Format: task.{task.id}
  spanId: text('span_id'),
  severityText: text('severity_text').notNull(),
  severityNumber: integer('severity_number').notNull(),
  body: text('body').notNull(),
  resource: jsonb('resource'),
  attributes: jsonb('attributes'),
  createdAt: timestamp('created_at', { mode: 'date' })
    .$defaultFn(() => new Date())
    .notNull(),
});

// Work items table - maintains array of task IDs
// Groups related tasks together so different work items' tasks don't get mixed up
export const workItems = pgTable('work_items', {
  id: serial('id').primaryKey(),
  projectId: integer('project_id').notNull(), // Reference to parent project - required
  name: text('name').notNull(),
  description: text('description'),
  status: text('status').notNull().default('active'), // 'active', 'completed', 'archived'
  // Upload step results - stored to skip upload step on return
  datasetId: integer('dataset_id'), // Selected dataset from upload step
  featureColumns: jsonb('feature_columns'), // Selected features as JSON array
  targetColumn: text('target_column'), // Selected target column
  // Tuning step results - stored to remember selected models
  selectedModels: jsonb('selected_models'), // Selected models as JSON array
  createdAt: timestamp('created_at', { mode: 'date' })
    .$defaultFn(() => new Date())
    .notNull(),
  updatedAt: timestamp('updated_at', { mode: 'date' })
    .$defaultFn(() => new Date())
    .notNull(),
});

// Projects table - organizes datasets and work items
export const projects = pgTable('projects', {
  id: serial('id').primaryKey(),
  createdBy: uuid('created_by').references(() => users.id),
  name: text('name').notNull(),
  description: text('description'),
  status: text('status').notNull().default('active'), // 'active', 'completed', 'archived'
  createdAt: timestamp('created_at', { mode: 'date' })
    .$defaultFn(() => new Date())
    .notNull(),
  updatedAt: timestamp('updated_at', { mode: 'date' })
    .$defaultFn(() => new Date())
    .notNull(),
});
