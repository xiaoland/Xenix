import { Context } from "hono";

import { AppError } from "../errors";
import logger from "../utils/logger";

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
        code: err.name
          .replace("Error", "")
          .toUpperCase()
          .replace(/([A-Z])/g, "_$1")
          .substring(1),
        error: err.message,
      },
      { status: err.statusCode as any }
    );
  }

  // Handle Zod validation errors
  if (err.name === "ZodError") {
    return c.json(
      {
        code: "VALIDATION_ERROR",
        error: "Validation failed",
        details: (err as any).errors,
      },
      { status: 400 }
    );
  }

  // Log unexpected errors
  logger.error({ err }, "Unexpected error");

  // Handle unexpected errors
  return c.json(
    {
      code: "INTERNAL_SERVER_ERROR",
      error: "Internal Server Error",
    },
    { status: 500 }
  );
};
