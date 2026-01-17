/**
 * Backend application constants
 * Centralized location for magic numbers and configuration values
 */

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
