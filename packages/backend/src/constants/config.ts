/**
 * Backend application constants
 * Centralized location for magic numbers and configuration values
 */

// Queue Configuration
export const QUEUE_CONFIG = {
  RETRY_DELAY: 2000, // 2 seconds
  COMPLETED_JOB_AGE: 24 * 3600, // 24 hours in seconds
  COMPLETED_JOB_COUNT: 1000,
  FAILED_JOB_AGE: 7 * 24 * 3600, // 7 days in seconds
} as const;

// Timeouts
export const TIMEOUTS = {
  ML_OPERATION: 300000, // 5 minutes
  PYTHON_SCRIPT: 300000, // 5 minutes
  DATABASE_QUERY: 30000, // 30 seconds
} as const;

// Limits
export const LIMITS = {
  MAX_FILE_SIZE: 100 * 1024 * 1024, // 100MB
  MAX_DATASET_ROWS: 1000000, // 1 million rows
} as const;

// Redis defaults
export const REDIS_DEFAULTS = {
  PORT: 6379,
  HOST: 'localhost',
} as const;
