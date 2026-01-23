/**
 * ML Backend Service - HTTP client for ML backend deployments
 *
 * Handles communication with ML backend via HTTP API.
 * Supports fire-and-forget execution with result checking.
 */

import type { InferSelectModel } from "drizzle-orm";
import { MLBackendDeploymentRepository } from "../repositories/MLBackendDeploymentRepository";
import { mlBackendDeployments } from "../database/schema";
import { createStorageService } from "../storage";
import logger from "../utils/logger";

type MLBackendDeployment = InferSelectModel<typeof mlBackendDeployments>;

export interface ExecuteOptions {
  operation: string; // 'batch-train', 'single-train', 'predict'
  data: Record<string, any>; // Operation data including task_id
}

export interface TaskResult {
  // For training operations
  metrics?: { r2?: number; mse?: number; mae?: number; [key: string]: any };
  bestParams?: Record<string, any>; // batch-train only (camelCase converted from best_params)

  // For predict operations
  fittedModelPath?: string; // camelCase converted from fitted_model_path
  predictedDataPath?: string; // predict-file only (camelCase converted from predicted_data_path)
  predictedData?: any[]; // predict-inline only (camelCase converted from predicted_data)

  // Error handling
  error?: string;
  traceback?: string;
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
   * Prepare HTTP headers with custom headers from deployment configuration
   */
  private prepareHeaders(
    deployment: MLBackendDeployment,
    baseHeaders: Record<string, string> = {},
  ): Record<string, string> {
    const headers = { ...baseHeaders };

    // Add custom headers from deployment configuration
    if (deployment.headers && typeof deployment.headers === "object") {
      Object.entries(deployment.headers).forEach(([key, value]) => {
        if (typeof value === "string") {
          headers[key] = value;
        }
      });
    }

    return headers;
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

      // Prepare headers with custom headers from deployment
      const headers = this.prepareHeaders(deployment, {
        "Content-Type": "application/json",
      });

      const response = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
        // Allow connection to close after response
        signal: AbortSignal.timeout(5000), // 5 second timeout for initial response
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`ML backend returned ${response.status}: ${text}`);
      }

      logger.info(
        {
          deploymentId: deployment.id,
          taskId,
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
      return this.checkResultFromFilesystem(taskId);
    } else if (storageType === "local") {
      return this.checkResultFromHTTP(deployment, taskId);
    } else {
      throw new Error(
        `Unknown storage type '${storageType}' for deployment ${deployment.id}`,
      );
    }
  }

  /**
   * Convert snake_case keys to camelCase
   */
  private convertSnakeToCamel(obj: any): any {
    if (obj === null || obj === undefined) return obj;
    if (Array.isArray(obj))
      return obj.map((item) => this.convertSnakeToCamel(item));
    if (typeof obj !== "object") return obj;

    const converted: any = {};
    for (const [key, value] of Object.entries(obj)) {
      const camelKey = key.replace(/_([a-z])/g, (_, letter) =>
        letter.toUpperCase(),
      );
      converted[camelKey] = this.convertSnakeToCamel(value);
    }
    return converted;
  }

  /**
   * Transform file path for ML backend
   * With mounted filesystem, paths are passed through unchanged
   */
  private async transformPathForStorage(
    path: string,
    deployment: MLBackendDeployment,
  ): Promise<string> {
    // All storage is now filesystem-based, pass through unchanged
    return path;
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
      // Prepare headers with custom headers from deployment
      const headers = this.prepareHeaders(deployment, {
        Accept: "application/json",
      });

      const response = await fetch(url, {
        method: "GET",
        headers,
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

      const rawResult = await response.json();

      // Convert snake_case to camelCase
      const result = this.convertSnakeToCamel(rawResult) as TaskResult;

      logger.info(
        {
          deploymentId: deployment.id,
          taskId,
        },
        "Retrieved task result from ML backend via HTTP",
      );

      return result;
    } catch (error) {
      return null;
    }
  }

  /**
   * Check result from filesystem storage
   * Uses storage service to fetch results from mounted OSS or local filesystem
   */
  private async checkResultFromFilesystem(
    taskId: number,
  ): Promise<TaskResult | null> {
    const resultKey = `tasks/${taskId}/result.json`;
    const storage = createStorageService();

    try {
      // Fetch result from filesystem storage
      const response = await storage.fetch(resultKey, {
        timeout: 3000,
        abs: true,
      });

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

      const rawResult = await response.json();

      // Convert snake_case to camelCase
      const result = this.convertSnakeToCamel(rawResult) as TaskResult;

      logger.info(
        {
          taskId,
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
   * Check task status from status.txt file
   */
  async checkStatus(
    deployment: MLBackendDeployment,
    taskId: number,
  ): Promise<"pending" | "running" | "completed" | "failed" | null> {
    const storageType = deployment.storage || "local";

    try {
      if (storageType === "oss") {
        const storage = createStorageService();
        const statusKey = `tasks/${taskId}/status.txt`;
        const response = await storage.fetch(statusKey, { timeout: 2000 });
        if (!response.ok) return null;
        const text = await response.text();
        return text.trim() as any;
      } else {
        const url = `${deployment.apiUrl}/tasks/${taskId}/status`;

        // Prepare headers with custom headers from deployment
        const headers = this.prepareHeaders(deployment);

        const response = await fetch(url, {
          headers: Object.keys(headers).length > 0 ? headers : undefined,
          signal: AbortSignal.timeout(2000),
        });
        if (!response.ok) return null;
        const text = await response.text();
        return text.trim() as any;
      }
    } catch (error) {
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
      trainDataPath: string;
      model: string;
      featureColumns: string[];
      targetColumn: string;
      paramGrid?: Record<string, any[]>;
    },
  ): Promise<void> {
    const deployment = await this.getDeployment(deploymentId);

    // Transform path for storage type
    const transformedPath = await this.transformPathForStorage(
      options.trainDataPath,
      deployment,
    );

    await this.execute(deployment, {
      operation: "batch-train",
      data: {
        task_id: taskId,
        train_data_path: transformedPath,
        model: options.model,
        feature_columns: options.featureColumns,
        target_columns: [options.targetColumn],
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
      trainDataPath: string;
      model: string;
      featureColumns: string[];
      targetColumn: string;
      params: Record<string, any>;
      parentTaskId?: number;
    },
  ): Promise<void> {
    const deployment = await this.getDeployment(deploymentId);

    // Transform path for storage type
    const transformedPath = await this.transformPathForStorage(
      options.trainDataPath,
      deployment,
    );

    await this.execute(deployment, {
      operation: "single-train",
      data: {
        task_id: taskId,
        train_data_path: transformedPath,
        model: options.model,
        feature_columns: options.featureColumns,
        target_columns: [options.targetColumn],
        params: options.params,
        parent_task_id: options.parentTaskId,
      },
    });
  }

  /**
   * Predict operation (file-based)
   */
  async predictFile(
    deploymentId: number,
    taskId: number,
    options: {
      trainDataPath: string;
      toPredictDataPath: string;
      model: string;
      params: Record<string, any>;
      featureColumns: string[];
      targetColumn: string;
    },
  ): Promise<void> {
    const deployment = await this.getDeployment(deploymentId);

    // Transform paths for storage type
    const transformedTrainPath = await this.transformPathForStorage(
      options.trainDataPath,
      deployment,
    );
    const transformedPredictPath = await this.transformPathForStorage(
      options.toPredictDataPath,
      deployment,
    );

    await this.execute(deployment, {
      operation: "predict-file",
      data: {
        task_id: taskId,
        train_data_path: transformedTrainPath,
        to_predict_data_path: transformedPredictPath,
        model: options.model,
        params: options.params,
        feature_columns: options.featureColumns,
        target_columns: [options.targetColumn],
      },
    });
  }

  /**
   * Predict operation (inline data)
   */
  async predictInline(
    deploymentId: number,
    taskId: number,
    options: {
      trainDataPath: string;
      toPredictData: any[];
      model: string;
      params: Record<string, any>;
      featureColumns: string[];
      targetColumn: string;
    },
  ): Promise<void> {
    const deployment = await this.getDeployment(deploymentId);

    // Transform train data path for storage type
    const transformedTrainPath = await this.transformPathForStorage(
      options.trainDataPath,
      deployment,
    );

    await this.execute(deployment, {
      operation: "predict-inline",
      data: {
        task_id: taskId,
        train_data_path: transformedTrainPath,
        to_predict_data: options.toPredictData,
        model: options.model,
        params: options.params,
        feature_columns: options.featureColumns,
        target_columns: [options.targetColumn],
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
