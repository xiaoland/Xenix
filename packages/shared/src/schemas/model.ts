/**
 * Model Zod schemas for validation
 */
import { z } from "zod";

export const ModelMetadataSchema = z.object({
  name: z.string(),
  displayName: z.string(),
  category: z.string(),
  description: z.string().optional(),
  parameters: z.record(z.any()).optional(),
});

export const ModelIdParamSchema = z.object({
  id: z.string().min(1, "Model name is required"),
});

export const ModelOptionSchema = z.object({
  label: z.string(),
  value: z.string(),
});

export type ModelOption = z.infer<typeof ModelOptionSchema>;
