/**
 * Prediction-related Zod schemas for validation
 */

import { z } from 'zod';

export const InlinePredictSchema = z.object({
  workItemId: z.number(),
  model: z.string(),
  tuningTaskId: z.number(),
  predictionData: z.array(z.record(z.any())).min(1),
});

export type InlinePredictDto = z.infer<typeof InlinePredictSchema>;
