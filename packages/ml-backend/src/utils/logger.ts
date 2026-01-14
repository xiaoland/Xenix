import pg from 'pg';
import type { MLLogger } from '../types';

const { Pool } = pg;

/**
 * Logger configuration
 */
export interface LoggerConfig {
  databaseUrl: string;
  serviceName?: string;
  serviceVersion?: string;
}

/**
 * Database logger for ML operations
 * Writes logs directly to the database using OpenTelemetry format
 */
export class DatabaseLogger implements MLLogger {
  private pool: pg.Pool;
  private traceId: string;
  private serviceName: string;
  private serviceVersion: string;

  constructor(config: LoggerConfig, taskId: number) {
    this.pool = new Pool({
      connectionString: config.databaseUrl,
    });
    this.traceId = `task.${taskId}`;
    this.serviceName = config.serviceName || 'xenix-ml-backend';
    this.serviceVersion = config.serviceVersion || '1.0.0';
  }

  /**
   * Log a message to the database
   */
  async log(
    message: string,
    level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL',
    attributes?: Record<string, any>
  ): Promise<void> {
    const severityNumber = this.getSeverityNumber(level);
    const timestamp = Date.now() * 1000000; // Convert to nanoseconds

    try {
      const client = await this.pool.connect();
      try {
        await client.query(
          `INSERT INTO logs (
            timestamp,
            observed_timestamp,
            trace_id,
            severity_text,
            severity_number,
            body,
            attributes,
            resource,
            created_at
          ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())`,
          [
            timestamp.toString(),
            timestamp.toString(),
            this.traceId,
            level,
            severityNumber,
            message,
            JSON.stringify(attributes || {}),
            JSON.stringify({
              'service.name': this.serviceName,
              'service.version': this.serviceVersion,
            }),
          ]
        );
      } finally {
        client.release();
      }
    } catch (error) {
      // Fallback to console if database write fails
      console.error('Failed to write log to database:', error);
      console.log(
        JSON.stringify({
          type: 'log',
          data: {
            timestamp,
            observed_timestamp: timestamp,
            severity_text: level,
            severity_number: severityNumber,
            body: message,
            resource: {
              'service.name': this.serviceName,
              'service.version': this.serviceVersion,
            },
            attributes: attributes || {},
          },
        })
      );
    }
  }

  /**
   * Get OpenTelemetry severity number from level string
   */
  private getSeverityNumber(
    level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'
  ): number {
    const levels: Record<string, number> = {
      DEBUG: 1,
      INFO: 9,
      WARNING: 13,
      ERROR: 17,
      CRITICAL: 21,
    };
    return levels[level] || 9;
  }

  /**
   * Close the database connection pool
   */
  async close(): Promise<void> {
    await this.pool.end();
  }
}

/**
 * Console logger for testing and development
 * Outputs structured logs to console instead of database
 */
export class ConsoleLogger implements MLLogger {
  private traceId: string;

  constructor(taskId: number) {
    this.traceId = `task.${taskId}`;
  }

  async log(
    message: string,
    level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL',
    attributes?: Record<string, any>
  ): Promise<void> {
    const timestamp = Date.now() * 1000000;
    const severityNumber = this.getSeverityNumber(level);

    console.log(
      JSON.stringify({
        type: 'log',
        data: {
          timestamp,
          observed_timestamp: timestamp,
          trace_id: this.traceId,
          severity_text: level,
          severity_number: severityNumber,
          body: message,
          resource: {
            'service.name': 'xenix-ml-backend',
            'service.version': '1.0.0',
          },
          attributes: attributes || {},
        },
      })
    );
  }

  private getSeverityNumber(level: string): number {
    const levels: Record<string, number> = {
      DEBUG: 1,
      INFO: 9,
      WARNING: 13,
      ERROR: 17,
      CRITICAL: 21,
    };
    return levels[level] || 9;
  }
}

/**
 * Create a logger instance based on environment
 */
export function createLogger(
  taskId: number,
  config?: LoggerConfig
): MLLogger {
  if (config?.databaseUrl) {
    return new DatabaseLogger(config, taskId);
  }
  return new ConsoleLogger(taskId);
}
