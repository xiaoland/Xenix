import { Context } from 'hono';
import { AppError } from '../errors/index.js';

/**
 * Global error handler middleware
 * Handles all errors thrown in the application
 * 
 * Error response format (HTTP semantics pattern):
 * {
 *   code: string,      // Error code (e.g., "UNAUTHORIZED", "NOT_FOUND")
 *   error: string      // Human-readable error message
 * }
 */
export const errorHandler = (err: Error, c: Context) => {
  // Handle custom AppError instances
  if (err instanceof AppError) {
    return c.json(
      {
        code: err.name.replace('Error', '').toUpperCase().replace(/([A-Z])/g, '_$1').substring(1),
        error: err.message,
      },
      err.statusCode
    );
  }

  // Handle Zod validation errors
  if (err.name === 'ZodError') {
    return c.json(
      {
        code: 'VALIDATION_ERROR',
        error: 'Validation failed',
        details: (err as any).errors,
      },
      400
    );
  }

  // Log unexpected errors
  console.error('Unexpected error:', err);

  // Handle unexpected errors
  return c.json(
    {
      code: 'INTERNAL_SERVER_ERROR',
      error: 'Internal Server Error',
    },
    500
  );
};
