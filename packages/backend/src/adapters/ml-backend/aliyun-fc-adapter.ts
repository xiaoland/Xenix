/**
 * Aliyun FC Adapter for ML Backend
 *
 * Invokes ml-backend by calling Aliyun Function Compute functions asynchronously.
 * Used for production deployment.
 *
 * I/O Characteristics:
 * - Uses OSS object keys (not full paths)
 * - OSS bucket is mounted at /mnt/oss in FC environment
 * - ml-backend reads from /mnt/oss/<key>
 * - Results (best-params, metrics) are saved to database directly by ml-backend
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

/**
 * Aliyun FC Adapter - Invokes ml-backend via Aliyun Function Compute
 */
export class AliyunFCAdapter implements MLBackendAdapter {
  constructor() {
    // Check if FC is configured
    if (this.isAvailable()) {
      logger.info("AliyunFCAdapter initialized");
    } else {
      logger.warn(
        "AliyunFCAdapter not available - FC client not configured"
      );
    }
  }

  isAvailable(): boolean {
    return fcInvokeService.isAvailable();
  }

  async batchTrain(options: BatchTrainRequest): Promise<void> {
    if (!this.isAvailable()) {
      throw new Error("AliyunFCAdapter is not available");
    }

    // Invoke ml-batch-train-worker function
    await fcInvokeService.invokeAsync({
      functionName: "ml-batch-train-worker",
      payload: {
        taskId: options.taskId,
        inputFile: options.inputFile, // OSS key, FC will read from /mnt/oss/<key>
        model: options.model,
        featureColumns: options.featureColumns,
        targetColumn: options.targetColumn,
        paramGrid: options.paramGrid || {},
      },
    });

    logger.info(
      { taskId: options.taskId, model: options.model },
      "Auto-tune task invoked via FC"
    );
  }

  async singleTrain(options: SingleTrainRequest): Promise<void> {
    if (!this.isAvailable()) {
      throw new Error("AliyunFCAdapter is not available");
    }

    // Invoke ml-single-train-worker function
    await fcInvokeService.invokeAsync({
      functionName: "ml-single-train-worker",
      payload: {
        taskId: options.taskId,
        inputFile: options.inputFile, // OSS key, FC will read from /mnt/oss/<key>
        model: options.model,
        featureColumns: options.featureColumns,
        targetColumn: options.targetColumn,
        params: options.parameters,
        parentTaskId: options.parentTaskId,
      },
    });

    logger.info(
      { taskId: options.taskId, model: options.model },
      "Manual-tune task invoked via FC"
    );
  }

  async predict(options: PredictRequest): Promise<void> {
    if (!this.isAvailable()) {
      throw new Error("AliyunFCAdapter is not available");
    }

    // Invoke ml-predict-worker function
    await fcInvokeService.invokeAsync({
      functionName: "ml-predict-worker",
      payload: {
        taskId: options.taskId,
        trainData: options.trainingDataPath, // OSS key
        predictData: options.predictionData, // OSS key or inline data
        outputPath: options.outputPath, // OSS key
        model: options.model,
        params: options.params,
        featureColumns: options.featureColumns,
        targetColumn: options.targetColumn,
      },
    });

    logger.info(
      { taskId: options.taskId, model: options.model },
      "Predict task invoked via FC"
    );
  }
}
