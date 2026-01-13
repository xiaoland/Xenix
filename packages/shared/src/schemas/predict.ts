/**
 * Prediction-related Zod schemas for validation
 */
import { z } from 'zod';

// More specific schema for prediction data values (valid JSON types)
const PredictionValueSchema = z.union([
  z.string(),
  z.number(),
  z.boolean(),
  z.null(),
]);

export const InlinePredictSchema = z.object({
  workItemId: z.number(),
  model: z.string(),
  tuningTaskId: z.number(),
  predictionData: z.array(z.record(PredictionValueSchema)).min(1),
});

export type InlinePredictDto = z.infer<typeof InlinePredictSchema>;
