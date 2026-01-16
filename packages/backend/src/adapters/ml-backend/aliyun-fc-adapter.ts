/**
 * Aliyun FC Adapter for ML Backend
 *
 * Invokes ml-backend by calling Aliyun Function Compute functions asynchronously.
 * Used for production deployment.
 *
 * I/O Characteristics:
 * - Uses task-specific base paths: /mnt/oss/tasks/{taskId}
 * - OSS bucket is mounted at /mnt/oss in FC environment
 * - ml-backend reads from base_path (passed via fc_handler.py)
 * - Results are saved to database directly by ml-backend
 * - Logs are written to database directly by ml-backend
 */

import { fcInvokeService } from "../../services/FCInvokeService";
import logger from "../../utils/logger";
import type {
  MLBackendAdapter,
  BatchTrainRequest,
  SingleTrainRequest,
  PredictRequest,
} from "./interface";
import type { AliyunFCAdapterParams } from "../../types/ml-backend";

/**
 * Aliyun FC Adapter - Invokes ml-backend via Aliyun Function Compute
 */
export class AliyunFCAdapter implements MLBackendAdapter {
  private params: AliyunFCAdapterParams;

  constructor(params: AliyunFCAdapterParams) {
    this.params = params;

    // Check if FC is configured
    if (this.isAvailable()) {
      logger.info(
        { serviceName: params.serviceName },
        "AliyunFCAdapter initialized"
      );
    } else {
      logger.warn(
        "AliyunFCAdapter not available - FC client not configured"
      );
    }
  }

  isAvailable(): boolean {
    return fcInvokeService.isAvailable();
  }

  /**
   * Get task-specific base path for FC environment
   */
  private getTaskBasePath(taskId: number): string {
    const baseOSSPath = this.params.basePath || "/mnt/oss";
    return `${baseOSSPath}/tasks/${taskId}`;
  }

  async batchTrain(options: BatchTrainRequest): Promise<void> {
    if (!this.isAvailable()) {
      throw new Error("AliyunFCAdapter is not available");
    }

    const taskBasePath = this.getTaskBasePath(options.taskId);

    // Invoke ml-batch-train-worker function with new Python format
    await fcInvokeService.invokeAsync({
      functionName: "ml-batch-train-worker",
      payload: {
        operation: "batch-train",
        basePath: taskBasePath,
        data: {
          task_id: options.taskId,
          input_file: options.inputFile,
          model: options.model,
          feature_columns: options.featureColumns,
          target_column: options.targetColumn,
          param_grid: options.paramGrid || {},
        },
      },
    });

    logger.info(
      {
        taskId: options.taskId,
        model: options.model,
        basePath: taskBasePath,
      },
      "Batch-train task invoked via FC"
    );
  }

  async singleTrain(options: SingleTrainRequest): Promise<void> {
    if (!this.isAvailable()) {
      throw new Error("AliyunFCAdapter is not available");
    }

    const taskBasePath = this.getTaskBasePath(options.taskId);

    // Invoke ml-single-train-worker function with new Python format
    await fcInvokeService.invokeAsync({
      functionName: "ml-single-train-worker",
      payload: {
        operation: "single-train",
        basePath: taskBasePath,
        data: {
          task_id: options.taskId,
          input_file: options.inputFile,
          model: options.model,
          feature_columns: options.featureColumns,
          target_column: options.targetColumn,
          parameters: options.parameters,
          parent_task_id: options.parentTaskId,
        },
      },
    });

    logger.info(
      {
        taskId: options.taskId,
        model: options.model,
        basePath: taskBasePath,
      },
      "Single-train task invoked via FC"
    );
  }

  async predict(options: PredictRequest): Promise<void> {
    if (!this.isAvailable()) {
      throw new Error("AliyunFCAdapter is not available");
    }

    const taskBasePath = this.getTaskBasePath(options.taskId);

    // Invoke ml-predict-worker function with new Python format
    await fcInvokeService.invokeAsync({
      functionName: "ml-predict-worker",
      payload: {
        operation: "predict",
        basePath: taskBasePath,
        data: {
          task_id: options.taskId,
          training_data_path: options.trainingDataPath,
          prediction_data: options.predictionData,
          output_path: options.outputPath,
          model: options.model,
          parameters: options.params,
          feature_columns: options.featureColumns,
          target_column: options.targetColumn,
        },
      },
    });

    logger.info(
      {
        taskId: options.taskId,
        model: options.model,
        basePath: taskBasePath,
      },
      "Predict task invoked via FC"
    );
  }
}
