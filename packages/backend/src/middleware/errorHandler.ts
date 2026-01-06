import { Context } from 'hono';
import { AppError } from '../errors/index.js';

/**
 * Global error handler middleware
 * Handles all errors thrown in the application
 */
export const errorHandler = (err: Error, c: Context) => {
  // Handle custom AppError instances
  if (err instanceof AppError) {
    return c.json(
      {
        success: false,
        error: err.message,
      },
      err.statusCode
    );
  }

  // Handle Zod validation errors
  if (err.name === 'ZodError') {
    return c.json(
      {
        success: false,
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
      success: false,
      error: 'Internal Server Error',
    },
    500
  );
};
