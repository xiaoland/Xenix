/**
 * ML Backend Deployment Zod schemas for validation
 */
import { z } from 'zod';

export const MLBackendDeploymentSchema = z.object({
  id: z.number(),
  name: z.string(),
  createdBy: z.string().uuid().optional(),
  apiUrl: z.string().url(),
  proxy: z.string().optional(),
  storage: z.enum(["local", "oss"]),
  createdAt: z.string().datetime(),
});

export type MLBackendDeployment = z.infer<typeof MLBackendDeploymentSchema>;
