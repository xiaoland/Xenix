/**
 * Task Zod schemas for validation
 */

import { z } from 'zod';

export const TaskStatusSchema = z.enum(['pending', 'running', 'completed', 'failed']);

export const AutoTuneTaskParameterSchema = z.object({
  model: z.string(),
  datasetId: z.number(),
  featureColumns: z.array(z.string()),
  targetColumn: z.string(),
  paramGrid: z.record(z.array(z.any())).optional(),
});

export const ManualTuneTaskParameterSchema = z.object({
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

export const AutoTuneTaskResultSchema = z.object({
  params: z.record(z.any()),
  metrics: z.record(z.any()),
  bestScore: z.number().optional(),
});

export const ManualTuneTaskResultSchema = z.object({
  params: z.record(z.any()),
  metrics: z.record(z.any()),
});

export const PredictTaskResultSchema = z.object({
  outputFile: z.string(),
  rowCount: z.number(),
});

export const AutoTuneTaskSchema = z.object({
  id: z.number(),
  workItemId: z.number().optional(),
  type: z.literal('auto-tune'),
  status: TaskStatusSchema,
  parameter: AutoTuneTaskParameterSchema,
  result: AutoTuneTaskResultSchema.optional(),
  error: z.string().optional(),
  createdAt: z.string().datetime().optional(),
});

export const ManualTuneTaskSchema = z.object({
  id: z.number(),
  workItemId: z.number().optional(),
  type: z.literal('manual-tune'),
  status: TaskStatusSchema,
  parameter: ManualTuneTaskParameterSchema,
  result: ManualTuneTaskResultSchema.optional(),
  error: z.string().optional(),
  createdAt: z.string().datetime().optional(),
});

export const PredictTaskSchema = z.object({
  id: z.number(),
  workItemId: z.number().optional(),
  type: z.literal('predict'),
  status: TaskStatusSchema,
  parameter: PredictTaskParameterSchema,
  result: PredictTaskResultSchema.optional(),
  error: z.string().optional(),
  createdAt: z.string().datetime().optional(),
});

export const TaskSchema = z.discriminatedUnion('type', [
  AutoTuneTaskSchema,
  ManualTuneTaskSchema,
  PredictTaskSchema,
]);

export const CreateAutoTuneTaskSchema = z.object({
  workItemId: z.number().optional(),
  model: z.string(),
  datasetId: z.number().optional(),
  featureColumns: z.array(z.string()).min(1).optional(),
  targetColumn: z.string().optional(),
  paramGrid: z.record(z.array(z.any())).optional(),
});

export const CreateManualTuneTaskSchema = z.object({
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
export type AutoTuneTaskParameter = z.infer<typeof AutoTuneTaskParameterSchema>;
export type ManualTuneTaskParameter = z.infer<typeof ManualTuneTaskParameterSchema>;
export type PredictTaskParameter = z.infer<typeof PredictTaskParameterSchema>;
export type AutoTuneTaskResult = z.infer<typeof AutoTuneTaskResultSchema>;
export type ManualTuneTaskResult = z.infer<typeof ManualTuneTaskResultSchema>;
export type PredictTaskResult = z.infer<typeof PredictTaskResultSchema>;
export type AutoTuneTask = z.infer<typeof AutoTuneTaskSchema>;
export type ManualTuneTask = z.infer<typeof ManualTuneTaskSchema>;
export type PredictTask = z.infer<typeof PredictTaskSchema>;
export type Task = z.infer<typeof TaskSchema>;
export type CreateAutoTuneTaskDto = z.infer<typeof CreateAutoTuneTaskSchema>;
export type CreateManualTuneTaskDto = z.infer<typeof CreateManualTuneTaskSchema>;
export type CreatePredictTaskDto = z.infer<typeof CreatePredictTaskSchema>;
