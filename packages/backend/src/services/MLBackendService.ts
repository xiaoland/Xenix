/**
 * ML Backend Service - HTTP client for ML backend deployments
 *
 * Handles communication with ML backend via HTTP API.
 * Supports fire-and-forget execution with result checking.
 */

import type { InferSelectModel } from "drizzle-orm";
import { MLBackendDeploymentRepository } from "../repositories/MLBackendDeploymentRepository";
import { mlBackendDeployments } from "../database/schema";
import { storage } from "../storage";
import logger from "../utils/logger";

type MLBackendDeployment = InferSelectModel<typeof mlBackendDeployments>;

export interface ExecuteOptions {
  operation: string; // 'batch-train', 'single-train', 'predict'
  data: Record<string, any>; // Operation data including task_id
}

export interface TaskResult {
  status: "pending" | "completed" | "failed" | "error";
  result?: any;
  error?: string;
  traceback?: string;
  message?: string;
}

export class MLBackendService {
  private deploymentRepo: MLBackendDeploymentRepository;

  constructor() {
    this.deploymentRepo = new MLBackendDeploymentRepository();
  }

  /**
   * Get deployment by ID
   */
  private async getDeployment(
    deploymentId: number,
  ): Promise<MLBackendDeployment> {
    const deployment = await this.deploymentRepo.findById(deploymentId);
    if (!deployment) {
      throw new Error(`Deployment ${deploymentId} not found`);
    }
    return deployment;
  }

  /**
   * Execute ML operation via HTTP
   *
   * Makes POST request to deployment's API URL and returns immediately.
   * Task is processed in background by ML backend.
   *
   * @param deployment - ML backend deployment configuration
   * @param options - Operation type and data
   * @returns Promise that resolves when request is accepted (200)
   */
  async execute(
    deployment: MLBackendDeployment,
    options: ExecuteOptions,
  ): Promise<{ accepted: boolean; taskId: number }> {
    const taskId = options.data.task_id;

    if (!taskId) {
      throw new Error("task_id is required in operation data");
    }

    const apiUrl = deployment.apiUrl;
    if (!apiUrl) {
      throw new Error(
        `Deployment ${deployment.name} has no api_url configured`,
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
        "Executing ML operation via HTTP",
      );

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
        // Allow connection to close after response
        signal: AbortSignal.timeout(5000), // 5 second timeout for initial response
      });

      if (response.status !== 200) {
        const text = await response.text();
        throw new Error(`ML backend returned ${response.status}: ${text}`);
      }

      const result = await response.json();

      logger.info(
        {
          deploymentId: deployment.id,
          taskId,
          status: result.status,
        },
        "ML operation accepted by backend",
      );

      return { accepted: true, taskId };
    } catch (error) {
      logger.error(
        {
          deploymentId: deployment.id,
          taskId,
          error: error instanceof Error ? error.message : String(error),
        },
        "Failed to execute ML operation via HTTP",
      );

      throw error;
    }
  }

  /**
   * Check for task result
   * Retrieves result based on deployment's storage configuration:
   * - 'local': HTTP GET to {apiUrl}/tasks/{taskId}/result
   * - 'oss': Signed GET request to OSS bucket
   *
   * @param deployment - ML backend deployment configuration
   * @param taskId - Task ID
   * @returns Task result or null if not available
   */
  async checkResult(
    deployment: MLBackendDeployment,
    taskId: number,
  ): Promise<TaskResult | null> {
    const storageType = deployment.storage || "local";

    if (storageType === "oss") {
      return this.checkResultFromOSS(taskId);
    } else if (storageType === "local") {
      return this.checkResultFromHTTP(deployment, taskId);
    } else {
      throw new Error(
        `Unknown storage type '${storageType}' for deployment ${deployment.id}`,
      );
    }
  }

  /**
   * Check result via HTTP (local deployments)
   */
  private async checkResultFromHTTP(
    deployment: MLBackendDeployment,
    taskId: number,
  ): Promise<TaskResult | null> {
    const apiUrl = deployment.apiUrl;
    if (!apiUrl) {
      return null;
    }

    const url = `${apiUrl}/tasks/${taskId}/result`;

    try {
      const response = await fetch(url, {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
        signal: AbortSignal.timeout(3000),
      });

      if (response.status === 404 || response.status === 204) {
        return null;
      }

      if (!response.ok) {
        logger.warn(
          {
            deploymentId: deployment.id,
            taskId,
            status: response.status,
          },
          "Failed to check task result via HTTP",
        );
        return null;
      }

      const result = (await response.json()) as TaskResult;

      if (result.status === "pending") {
        return null;
      }

      logger.info(
        {
          deploymentId: deployment.id,
          taskId,
          resultStatus: result.status,
        },
        "Retrieved task result from ML backend via HTTP",
      );

      return result;
    } catch (error) {
      return null;
    }
  }

  /**
   * Check result from OSS storage (cloud deployments)
   * Uses storage service to fetch results
   */
  private async checkResultFromOSS(taskId: number): Promise<TaskResult | null> {
    const resultKey = `tasks/${taskId}/result.json`;

    try {
      // Fetch result from storage (uses aws4fetch internally for OSS)
      const response = await storage.fetch(resultKey, { timeout: 3000 });

      if (response.status === 404 || response.status === 204) {
        // Result not available yet
        return null;
      }

      if (!response.ok) {
        logger.warn(
          {
            taskId,
            status: response.status,
          },
          "Failed to check task result from storage",
        );
        return null;
      }

      const result = (await response.json()) as TaskResult;

      if (result.status === "pending") {
        return null;
      }

      logger.info(
        {
          taskId,
          resultStatus: result.status,
          storageKey: resultKey,
        },
        "Retrieved task result from storage",
      );

      return result;
    } catch (error) {
      logger.debug(
        {
          taskId,
          error: error instanceof Error ? error.message : String(error),
        },
        "Failed to read task result from storage",
      );
      return null;
    }
  }

  /**
   * Batch train operation
   */
  async batchTrain(
    deploymentId: number,
    taskId: number,
    options: {
      inputFile: string;
      model: string;
      featureColumns: string[];
      targetColumn: string;
      paramGrid?: Record<string, any[]>;
    },
  ): Promise<void> {
    const deployment = await this.getDeployment(deploymentId);

    await this.execute(deployment, {
      operation: "batch-train",
      data: {
        task_id: taskId,
        input_file: options.inputFile,
        model: options.model,
        feature_columns: options.featureColumns,
        target_column: options.targetColumn,
        param_grid: options.paramGrid || {},
      },
    });
  }

  /**
   * Single train operation
   */
  async singleTrain(
    deploymentId: number,
    taskId: number,
    options: {
      inputFile: string;
      model: string;
      featureColumns: string[];
      targetColumn: string;
      parameters: Record<string, any>;
      parentTaskId?: number;
    },
  ): Promise<void> {
    const deployment = await this.getDeployment(deploymentId);

    await this.execute(deployment, {
      operation: "single-train",
      data: {
        task_id: taskId,
        input_file: options.inputFile,
        model: options.model,
        feature_columns: options.featureColumns,
        target_column: options.targetColumn,
        parameters: options.parameters,
        parent_task_id: options.parentTaskId,
      },
    });
  }

  /**
   * Predict operation (file-based)
   */
  async predict(
    deploymentId: number,
    taskId: number,
    options: {
      trainingDataPath: string;
      predictionDataPath: string;
      outputPath: string;
      model: string;
      params: Record<string, any>;
      featureColumns: string[];
      targetColumn: string;
    },
  ): Promise<void> {
    const deployment = await this.getDeployment(deploymentId);

    await this.execute(deployment, {
      operation: "predict",
      data: {
        task_id: taskId,
        training_data_path: options.trainingDataPath,
        prediction_data_path: options.predictionDataPath,
        output_path: options.outputPath,
        model: options.model,
        parameters: options.params,
        feature_columns: options.featureColumns,
        target_column: options.targetColumn,
      },
    });
  }

  /**
   * Predict operation (file-based) - alias for predict
   */
  async predictFile(
    deploymentId: number,
    taskId: number,
    options: {
      trainingDataPath: string;
      predictionDataPath: string;
      outputPath: string;
      model: string;
      params: Record<string, any>;
      featureColumns: string[];
      targetColumn: string;
    },
  ): Promise<void> {
    return this.predict(deploymentId, taskId, options);
  }

  /**
   * Predict operation (inline data)
   */
  async predictInline(
    deploymentId: number,
    taskId: number,
    options: {
      trainingDataPath: string;
      predictionData: any[];
      outputPath: string;
      model: string;
      params: Record<string, any>;
      featureColumns: string[];
      targetColumn: string;
    },
  ): Promise<void> {
    const deployment = await this.getDeployment(deploymentId);

    await this.execute(deployment, {
      operation: "predict",
      data: {
        task_id: taskId,
        training_data_path: options.trainingDataPath,
        prediction_data: options.predictionData,
        output_path: options.outputPath,
        model: options.model,
        parameters: options.params,
        feature_columns: options.featureColumns,
        target_column: options.targetColumn,
      },
    });
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
