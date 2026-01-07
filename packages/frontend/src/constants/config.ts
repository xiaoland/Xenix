/**
 * Frontend application constants
 * Centralized location for magic numbers and configuration values
 */

// API Configuration
export const API_CONFIG = {
  DEFAULT_URL: 'http://localhost:3000',
  DEFAULT_TIMEOUT: 30000, // 30 seconds
} as const;

// Polling Configuration
export const POLLING_CONFIG = {
  DEFAULT_INTERVAL: 3000, // 3 seconds
  TASK_STATUS_INTERVAL: 3000, // 3 seconds
  MAX_RETRIES: 10,
} as const;

// UI Configuration
export const UI_CONFIG = {
  DEBOUNCE_DELAY: 300, // milliseconds
  TOAST_DURATION: 3000, // milliseconds
  MAX_FILE_SIZE: 50 * 1024 * 1024, // 50MB
} as const;

// Pagination
export const PAGINATION = {
  DEFAULT_PAGE_SIZE: 20,
  DEFAULT_PAGE: 1,
} as const;
