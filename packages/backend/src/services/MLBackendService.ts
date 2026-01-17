/**
 * ML Backend Service - HTTP client for ML backend deployments
 *
 * Handles communication with ML backend via HTTP API.
 * Supports fire-and-forget execution with result checking.
 */

import logger from '../utils/logger';
import type { MLBackendDeployment } from '../types/ml-backend';

export interface ExecuteOptions {
  operation: string; // 'batch-train', 'single-train', 'predict'
  data: Record<string, any>; // Operation data including task_id
}

export interface TaskResult {
  status: 'pending' | 'completed' | 'failed' | 'error';
  result?: any;
  error?: string;
  traceback?: string;
  message?: string;
}

export class MLBackendService {
  /**
   * Execute ML operation via HTTP
   *
   * Makes POST request to deployment's API URL and returns immediately.
   * Task is processed in background by ML backend.
   *
   * @param deployment - ML backend deployment configuration
   * @param options - Operation type and data
   * @returns Promise that resolves when request is accepted (202)
   */
  async execute(
    deployment: MLBackendDeployment,
    options: ExecuteOptions,
  ): Promise<{ accepted: boolean; taskId: number }> {
    const taskId = options.data.task_id;

    if (!taskId) {
      throw new Error('task_id is required in operation data');
    }

    const apiUrl = deployment.deployment_params.apiUrl;
    if (!apiUrl) {
      throw new Error(
        `Deployment ${deployment.name} has no apiUrl configured`,
      );
    }

    const url = `${apiUrl}/execute`;
    const payload = {
      operation: options.operation,
      data: options.data,
    };

    try {
      logger.info(
        {
          deploymentId: deployment.id,
          deploymentName: deployment.name,
          apiUrl,
          operation: options.operation,
          taskId,
        },
        'Executing ML operation via HTTP',
      );

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
        // Allow connection to close after response
        signal: AbortSignal.timeout(5000), // 5 second timeout for initial response
      });

      if (response.status !== 200) {
        const text = await response.text();
        throw new Error(
          `ML backend returned ${response.status}: ${text}`,
        );
      }

      const result = await response.json();

      logger.info(
        {
          deploymentId: deployment.id,
          taskId,
          status: result.status,
        },
        'ML operation accepted by backend',
      );

      return { accepted: true, taskId };
    } catch (error) {
      logger.error(
        {
          deploymentId: deployment.id,
          taskId,
          error: error instanceof Error ? error.message : String(error),
        },
        'Failed to execute ML operation via HTTP',
      );

      throw error;
    }
  }

  /**
   * Check for task result
   *
   * Attempts to read result.json from the deployment.
   * Returns null if result not available yet.
   *
   * @param deployment - ML backend deployment configuration
   * @param taskId - Task ID
   * @returns Task result or null if not available
   */
  async checkResult(
    deployment: MLBackendDeployment,
    taskId: number,
  ): Promise<TaskResult | null> {
    const apiUrl = deployment.deployment_params.apiUrl;
    if (!apiUrl) {
      return null;
    }

    const url = `${apiUrl}/tasks/${taskId}/result`;

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
        },
        signal: AbortSignal.timeout(3000), // 3 second timeout
      });

      if (response.status === 404 || response.status === 204) {
        // Result not available yet
        return null;
      }

      if (!response.ok) {
        logger.warn(
          {
            deploymentId: deployment.id,
            taskId,
            status: response.status,
          },
          'Failed to check task result',
        );
        return null;
      }

      const result: TaskResult = await response.json();

      // If status is still pending, return null
      if (result.status === 'pending') {
        return null;
      }

      logger.info(
        {
          deploymentId: deployment.id,
          taskId,
          resultStatus: result.status,
        },
        'Retrieved task result from ML backend',
      );

      return result;
    } catch (error) {
      // Don't log errors for result checking - it's expected to fail sometimes
      return null;
    }
  }
}

// Singleton instance
let mlBackendServiceInstance: MLBackendService | null = null;

/**
 * Get ML Backend Service singleton
 */
export function getMLBackendService(): MLBackendService {
  if (!mlBackendServiceInstance) {
    mlBackendServiceInstance = new MLBackendService();
  }
  return mlBackendServiceInstance;
}
