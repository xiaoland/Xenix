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

  // File uploads
  MAX_FILE_SIZE: z.coerce.number().default(100 * 1024 * 1024), // 100MB
  UPLOAD_DIR: z
    .string()
    .default(
      process.env.NODE_ENV === 'production' ? '/tmp/uploads' : './uploads'
    ),

  // OSS Configuration (required when dataset or deployment uses OSS storage)
  OSS_REGION: z.string().optional(),
  OSS_ACCESS_KEY_ID: z.string().optional(),
  OSS_ACCESS_KEY_SECRET: z.string().optional(),
  OSS_BUCKET: z.string().optional(),
  OSS_ENDPOINT: z.string().optional(),
  OSS_MOUNT_POINT: z.string().default('/mnt/oss'),

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
