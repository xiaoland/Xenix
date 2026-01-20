/**
 * Dataset Zod schemas for validation
 */
import { z } from 'zod';

export const DatasetSchema = z.object({
  id: z.number(),
  projectId: z.number().optional(),
  name: z.string(),
  description: z.string().optional(),
  fileName: z.string(),
  fileSize: z.number(),
  columns: z.array(z.string()),
  rowCount: z.number(),
  storage: z.enum(["local", "oss"]),
  createdAt: z.string().datetime(),
});

export const ColumnSelectionSchema = z.object({
  featureColumns: z.array(z.string()).min(1),
  targetColumn: z.string(),
  datasetId: z.number().optional(),
});

export const CreateDatasetSchema = z.object({
  projectId: z.number().optional(),
  name: z.string().min(1),
  description: z.string().optional(),
  fileName: z.string(),
  fileSize: z.number().positive(),
  columns: z.array(z.string()),
  rowCount: z.number().nonnegative(),
  storage: z.enum(["local", "oss"]).default("local"),
});

export type Dataset = z.infer<typeof DatasetSchema>;
export type ColumnSelection = z.infer<typeof ColumnSelectionSchema>;
export type CreateDatasetDto = z.infer<typeof CreateDatasetSchema>;

// ID param validation schema
export const DatasetIdParamSchema = z.object({
  id: z.string().regex(/^\d+$/, 'Must be a valid number'),
});

export type DatasetIdParam = z.infer<typeof DatasetIdParamSchema>;
