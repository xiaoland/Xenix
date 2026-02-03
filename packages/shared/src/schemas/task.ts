/**
 * Task Zod schemas for validation
 */
import { z } from "zod";

export const TaskStatusSchema = z.enum([
  "pending",
  "running",
  "completed",
  "failed",
]);

export const BatchTrainTaskParameterSchema = z.object({
  model: z.string(),
  datasetId: z.number(),
  featureColumns: z.array(z.string()),
  targetColumn: z.string(),
  paramGrid: z.record(z.array(z.any())).optional(),
});

export const SingleTrainTaskParameterSchema = z.object({
  model: z.string(),
  datasetId: z.number(),
  featureColumns: z.array(z.string()),
  targetColumn: z.string(),
  parameters: z.record(z.any()),
});

export const PredictTaskParameterSchema = z.object({
  model: z.string(),
  trainingDatasetId: z.number(),
  predictionDatasetId: z.number(),
  featureColumns: z.array(z.string()),
  targetColumn: z.string(),
  parameters: z.record(z.any()),
});

export const CodeExecutionTaskParameterSchema = z.object({
  code: z.string().min(1, "Code is required"),
  inputs: z.record(z.any()).optional(),
  timeout: z.number().min(1).max(3600).optional(),
});

export const BatchTrainTaskResultSchema = z.object({
  params: z.record(z.any()),
  metrics: z.record(z.any()),
  bestScore: z.number().optional(),
});

export const SingleTrainTaskResultSchema = z.object({
  params: z.record(z.any()),
  metrics: z.record(z.any()),
});

export const PredictTaskResultSchema = z.object({
  outputFile: z.string(),
  rowCount: z.number(),
});

export const CodeExecutionTaskResultSchema = z.object({
  output: z.string().optional(),
  error: z.string().optional(),
  result: z.any().optional(),
  executionTime: z.number().optional(),
});

export const BatchTrainTaskSchema = z.object({
  id: z.number(),
  workItemId: z.number().optional(),
  type: z.literal("batch-train"),
  status: TaskStatusSchema,
  parameter: BatchTrainTaskParameterSchema,
  result: BatchTrainTaskResultSchema.optional(),
  error: z.string().optional(),
  createdAt: z.string().datetime().optional(),
});

export const SingleTrainTaskSchema = z.object({
  id: z.number(),
  workItemId: z.number().optional(),
  type: z.literal("single-train"),
  status: TaskStatusSchema,
  parameter: SingleTrainTaskParameterSchema,
  result: SingleTrainTaskResultSchema.optional(),
  error: z.string().optional(),
  createdAt: z.string().datetime().optional(),
});

export const PredictTaskSchema = z.object({
  id: z.number(),
  workItemId: z.number().optional(),
  type: z.literal("predict"),
  status: TaskStatusSchema,
  parameter: PredictTaskParameterSchema,
  result: PredictTaskResultSchema.optional(),
  error: z.string().optional(),
  createdAt: z.string().datetime().optional(),
});

export const CodeExecutionTaskSchema = z.object({
  id: z.number(),
  workItemId: z.number().optional(),
  type: z.literal("code-execution"),
  status: TaskStatusSchema,
  parameter: CodeExecutionTaskParameterSchema,
  result: CodeExecutionTaskResultSchema.optional(),
  error: z.string().optional(),
  createdAt: z.string().datetime().optional(),
});

export const TaskSchema = z.discriminatedUnion("type", [
  BatchTrainTaskSchema,
  SingleTrainTaskSchema,
  PredictTaskSchema,
  CodeExecutionTaskSchema,
]);

export const CreateBatchTrainTaskSchema = z.object({
  workItemId: z.number().optional(),
  model: z.string(),
  datasetId: z.number().optional(),
  featureColumns: z.array(z.string()).min(1).optional(),
  targetColumn: z.string().optional(),
  paramGrid: z.record(z.array(z.any())).optional(),
});

export const CreateSingleTrainTaskSchema = z.object({
  workItemId: z.number().optional(),
  model: z.string(),
  datasetId: z.number().optional(),
  featureColumns: z.array(z.string()).min(1).optional(),
  targetColumn: z.string().optional(),
  parameters: z.record(z.any()),
});

export const CreatePredictTaskSchema = z.object({
  workItemId: z.number(),
  model: z.string(),
  trainingDatasetId: z.number(),
  predictionDatasetId: z.number(),
  featureColumns: z.array(z.string()).min(1),
  targetColumn: z.string(),
  parameters: z.record(z.any()),
});

export type TaskStatus = z.infer<typeof TaskStatusSchema>;
export type BatchTrainTaskParameter = z.infer<
  typeof BatchTrainTaskParameterSchema
>;
export type SingleTrainTaskParameter = z.infer<
  typeof SingleTrainTaskParameterSchema
>;
export type PredictTaskParameter = z.infer<typeof PredictTaskParameterSchema>;
export type CodeExecutionTaskParameter = z.infer<
  typeof CodeExecutionTaskParameterSchema
>;
export type BatchTrainTaskResult = z.infer<typeof BatchTrainTaskResultSchema>;
export type SingleTrainTaskResult = z.infer<typeof SingleTrainTaskResultSchema>;
export type PredictTaskResult = z.infer<typeof PredictTaskResultSchema>;
export type CodeExecutionTaskResult = z.infer<
  typeof CodeExecutionTaskResultSchema
>;
export type BatchTrainTask = z.infer<typeof BatchTrainTaskSchema>;
export type SingleTrainTask = z.infer<typeof SingleTrainTaskSchema>;
export type PredictTask = z.infer<typeof PredictTaskSchema>;
export type CodeExecutionTask = z.infer<typeof CodeExecutionTaskSchema>;
export type Task = z.infer<typeof TaskSchema>;
export type CreateBatchTrainTaskDto = z.infer<
  typeof CreateBatchTrainTaskSchema
>;
export type CreateSingleTrainTaskDto = z.infer<
  typeof CreateSingleTrainTaskSchema
>;
export type CreatePredictTaskDto = z.infer<typeof CreatePredictTaskSchema>;

export const CreateCodeExecutionTaskSchema = z.object({
  workItemId: z.number().optional(),
  code: z.string().min(1, "Code is required"),
  inputs: z.record(z.any()).optional(),
  timeout: z.number().min(1).max(3600).optional(),
});

export type CreateCodeExecutionTaskDto = z.infer<
  typeof CreateCodeExecutionTaskSchema
>;

// Query validation schemas
export const GetTasksQuerySchema = z.object({
  workItemId: z.string().regex(/^\d+$/, "Must be a valid number"),
  type: z.string().optional(),
});

export const DeleteTasksByModelQuerySchema = z.object({
  workItemId: z.string().regex(/^\d+$/, "Must be a valid number"),
  model: z.string().min(1),
});

export const DeleteFailedTasksQuerySchema = z.object({
  workItemId: z.string().regex(/^\d+$/, "Must be a valid number"),
});

export type GetTasksQuery = z.infer<typeof GetTasksQuerySchema>;
export type DeleteTasksByModelQuery = z.infer<
  typeof DeleteTasksByModelQuerySchema
>;
export type DeleteFailedTasksQuery = z.infer<
  typeof DeleteFailedTasksQuerySchema
>;

// Task ID param validation schema
export const TaskIdParamSchema = z.object({
  id: z.string().regex(/^\d+$/, "Must be a valid number"),
});

export type TaskIdParam = z.infer<typeof TaskIdParamSchema>;
