/**
 * Model Zod schemas for validation
 */

import { z } from 'zod';

export const ModelMetadataSchema = z.object({
  name: z.string(),
  displayName: z.string(),
  category: z.string(),
  description: z.string().optional(),
  parameters: z.record(z.any()).optional(),
});

export type ModelMetadata = z.infer<typeof ModelMetadataSchema>;
