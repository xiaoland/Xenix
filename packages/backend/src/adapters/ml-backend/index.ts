/**
 * ML Backend Adapter Factory
 *
 * Creates the appropriate adapter based on database worker configuration.
 * Adapters determine how to invoke ml-backend operations (local spawn vs FC invoke).
 */

import logger from "../../utils/logger";
import { MLBackendWorkerRepository } from "../../repositories/MLBackendWorkerRepository";
import type {
  SpawnAdapterParams,
  AliyunFCAdapterParams,
} from "../../types/ml-backend";
import { AliyunFCAdapter } from "./aliyun-fc-adapter";
import type { MLBackendAdapter } from "./interface";
import { SpawnAdapter } from "./spawn-adapter";

/**
 * Get ML Backend adapter based on worker configuration from database
 *
 * @param workerId - ID of the ml_backend_worker to use
 * @returns MLBackendAdapter instance configured for the specified worker
 * @throws Error if worker not found or inactive
 */
export async function getMLBackendAdapter(
  workerId: number
): Promise<MLBackendAdapter> {
  const workerRepo = new MLBackendWorkerRepository();
  const worker = await workerRepo.findById(workerId);

  if (!worker) {
    throw new Error(`ML backend worker ${workerId} not found`);
  }

  if (!worker.is_active) {
    throw new Error(
      `ML backend worker ${workerId} (${worker.name}) is inactive`
    );
  }

  logger.info(
    { workerId, workerName: worker.name, adapter: worker.adapter },
    "Creating ML backend adapter"
  );

  switch (worker.adapter) {
    case "aliyun-fc":
      return new AliyunFCAdapter(worker.adapter_params as AliyunFCAdapterParams);

    case "spawn":
      return new SpawnAdapter(worker.adapter_params as SpawnAdapterParams);

    default:
      throw new Error(
        `Unknown adapter type: ${worker.adapter} for worker ${workerId}`
      );
  }
}

/**
 * Get the default ML backend worker and create its adapter
 *
 * @returns MLBackendAdapter instance for the default worker
 * @throws Error if no default worker configured
 */
export async function getDefaultMLBackendAdapter(): Promise<MLBackendAdapter> {
  const workerRepo = new MLBackendWorkerRepository();
  const defaultWorker = await workerRepo.findDefaultWorker();

  if (!defaultWorker) {
    throw new Error(
      "No default ML backend worker configured. Please configure a default worker in ml_backend_workers table."
    );
  }

  return getMLBackendAdapter(defaultWorker.id);
}

// Re-export types
export type {
  MLBackendAdapter,
  BatchTrainRequest,
  SingleTrainRequest,
  PredictRequest,
} from "./interface";
