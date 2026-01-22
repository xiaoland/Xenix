/**
 * Type-safe configuration management with Zod validation
 * Validates environment variables at startup
 */
import { z } from 'zod';

const configSchema = z.object({
  // Environment
  NODE_ENV: z
    .enum(['development', 'production', 'test'])
    .default('development'),

  // Server
  BACKEND_PORT: z.coerce.number().default(3000),
  FRONTEND_URL: z.string().url(),

  // Database
  DATABASE_URL: z.string().url(),

  // Authentication
  JWT_SECRET: z.string().min(32, 'JWT_SECRET must be at least 32 characters'),

  // File uploads and storage
  MAX_FILE_SIZE: z.coerce.number().default(100 * 1024 * 1024), // 100MB
  STORAGE_BASE_PATH: z
    .string()
    .default(
      process.env.NODE_ENV === 'production' ? '/mnt/oss' : './uploads'
    ),

  // ML
  PYTHON_PATH: z.string().default('/usr/bin/python3'),
  ML_TIMEOUT: z.coerce.number().default(300000), // 5 minutes
});

/**
 * Validates and exports configuration
 * Throws error if any required environment variable is missing or invalid
 */
export const config = configSchema.parse(process.env);

export type Config = z.infer<typeof configSchema>;
