// SQLite database schema for Xenix

import { sqliteTable, text, integer } from "drizzle-orm/sqlite-core";

// Model metadata table for storing model information and ModelParam schemas
export const modelMetadata = sqliteTable("model_metadata", {
  id: integer("id", { mode: "number" }).primaryKey({ autoIncrement: true }),
  category: text("category").notNull(), // e.g., 'regression', 'classification'
  name: text("name").notNull().unique(), // e.g., 'regression.adaboost'
  label: text("label").notNull(), // Human-readable name, e.g., 'AdaBoost'
  paramSchema: text("param_schema", { mode: "json" }), // JSON schema from pydantic model
  createdAt: integer("created_at", { mode: "timestamp" })
    .$defaultFn(() => new Date())
    .notNull(),
  updatedAt: integer("updated_at", { mode: "timestamp" })
    .$defaultFn(() => new Date())
    .notNull(),
});

// Datasets table for data manager - stores uploaded data files for reuse
export const datasets = sqliteTable("datasets", {
  id: integer("id", { mode: "number" }).primaryKey({ autoIncrement: true }),
  projectId: integer("project_id", { mode: "number" }), // Reference to project
  name: text("name").notNull(),
  description: text("description"),
  filePath: text("file_path").notNull(),
  fileName: text("file_name").notNull(),
  fileSize: integer("file_size", { mode: "number" }),
  columns: text("columns", { mode: "json" }),
  rowCount: integer("row_count"),
  createdAt: integer("created_at", { mode: "timestamp" })
    .$defaultFn(() => new Date())
    .notNull(),
  updatedAt: integer("updated_at", { mode: "timestamp" })
    .$defaultFn(() => new Date())
    .notNull(),
});

// Consolidated tasks table
// Type values: 'auto-tune', 'train', 'predict'
export const tasks = sqliteTable("tasks", {
  id: integer("id", { mode: "number" }).primaryKey({ autoIncrement: true }),
  workItemId: integer("work_item_id", { mode: "number" }), // Reference to work item
  type: text("type").notNull(), // 'auto-tune', 'train', 'predict'
  parameter: text("parameter", { mode: "json" }), // Task parameters as JSON object
  result: text("result", { mode: "json" }), // Task results/metrics as JSON object
  status: text("status").notNull().default("pending"),
  error: text("error"),
  createdAt: integer("created_at", { mode: "timestamp" })
    .$defaultFn(() => new Date())
    .notNull(),
  startedAt: integer("started_at", { mode: "timestamp" }),
  endAt: integer("end_at", { mode: "timestamp" }),
});

// OpenTelemetry-compliant logs table
// trace_id format: task.{task.id} for task-related logs
export const logs = sqliteTable("logs", {
  id: integer("id", { mode: "number" }).primaryKey({ autoIncrement: true }),
  timestamp: integer("timestamp", { mode: "number" }).notNull(),
  observedTimestamp: integer("observed_timestamp", {
    mode: "number",
  }).notNull(),
  traceId: text("trace_id").notNull(), // Format: task.{task.id}
  spanId: text("span_id"),
  severityText: text("severity_text").notNull(),
  severityNumber: integer("severity_number").notNull(),
  body: text("body").notNull(),
  resource: text("resource", { mode: "json" }),
  attributes: text("attributes", { mode: "json" }),
  createdAt: integer("created_at", { mode: "timestamp" })
    .$defaultFn(() => new Date())
    .notNull(),
});

// Work items table - maintains array of task IDs
// Groups related tasks together so different work items' tasks don't get mixed up
export const workItems = sqliteTable("work_items", {
  id: integer("id", { mode: "number" }).primaryKey({ autoIncrement: true }),
  projectId: integer("project_id", { mode: "number" }).notNull(), // Reference to parent project - required
  name: text("name").notNull(),
  description: text("description"),
  status: text("status").notNull().default("active"), // 'active', 'completed', 'archived'
  // Upload step results - stored to skip upload step on return
  datasetId: integer("dataset_id", { mode: "number" }), // Selected dataset from upload step
  featureColumns: text("feature_columns", { mode: "json" }), // Selected features as JSON array
  targetColumn: text("target_column"), // Selected target column
  createdAt: integer("created_at", { mode: "timestamp" })
    .$defaultFn(() => new Date())
    .notNull(),
  updatedAt: integer("updated_at", { mode: "timestamp" })
    .$defaultFn(() => new Date())
    .notNull(),
});

// Projects table - organizes datasets and work items
export const projects = sqliteTable("projects", {
  id: integer("id", { mode: "number" }).primaryKey({ autoIncrement: true }),
  name: text("name").notNull(),
  description: text("description"),
  status: text("status").notNull().default("active"), // 'active', 'completed', 'archived'
  createdAt: integer("created_at", { mode: "timestamp" })
    .$defaultFn(() => new Date())
    .notNull(),
  updatedAt: integer("updated_at", { mode: "timestamp" })
    .$defaultFn(() => new Date())
    .notNull(),
});
