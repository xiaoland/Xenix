/**
 * Pino logger configuration
 * Provides structured logging throughout the application
 */
import pino from 'pino';

const isDevelopment = process.env.NODE_ENV === 'development';

export const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  transport: isDevelopment
    ? {
        target: 'pino-pretty',
        options: {
          colorize: true,
          translateTime: 'HH:MM:ss Z',
          ignore: 'pid,hostname',
        },
      }
    : undefined,
  formatters: {
    level: (label) => {
      return { level: label };
    },
  },
});

/**
 * Create a child logger with additional context
 * @param bindings - Additional context to include in logs
 */
export const createLogger = (bindings: Record<string, any>) => {
  return logger.child(bindings);
};

export default logger;
