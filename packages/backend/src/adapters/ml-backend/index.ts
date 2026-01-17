/**
 * ML Backend Adapter Factory
 *
 * Creates the appropriate adapter based on database deployment configuration.
 * Adapters determine how to invoke ml-backend operations (local spawn vs FC invoke).
 */

import logger from "../../utils/logger";
import { MLBackendDeploymentRepository } from "../../repositories/MLBackendDeploymentRepository";
import type {
  SpawnAdapterParams,
  AliyunFCAdapterParams,
} from "../../types/ml-backend";
import { AliyunFCAdapter } from "./aliyun-fc-adapter";
import type { MLBackendAdapter } from "./interface";
import { SpawnAdapter } from "./spawn-adapter";

/**
 * Get ML Backend adapter based on deployment configuration from database
 *
 * @param deploymentId - ID of the ml_backend_deployment to use
 * @returns MLBackendAdapter instance configured for the specified deployment
 * @throws Error if deployment not found or inactive
 */
export async function getMLBackendAdapter(
  deploymentId: number
): Promise<MLBackendAdapter> {
  const deploymentRepo = new MLBackendDeploymentRepository();
  const deployment = await deploymentRepo.findById(deploymentId);

  if (!deployment) {
    throw new Error(`ML backend deployment ${deploymentId} not found`);
  }

  if (!deployment.is_active) {
    throw new Error(
      `ML backend deployment ${deploymentId} (${deployment.name}) is inactive`
    );
  }

  logger.info(
    { deploymentId, deploymentName: deployment.name, deploymentType: deployment.deployment_type },
    "Creating ML backend adapter"
  );

  // Legacy support: map old deployment types to adapter types
  const deploymentType = deployment.deployment_type;
  const params = deployment.deployment_params;

  // For now, keep adapter logic for backwards compatibility
  // This will be replaced with HTTP calls in the next phase
  if (deploymentType === 'http' || deploymentType === 'http-proxy-frontend') {
    // Temporary: treat http deployments as spawn for now
    return new SpawnAdapter(params as SpawnAdapterParams);
  }

  throw new Error(
    `Unknown deployment type: ${deploymentType} for deployment ${deploymentId}`
  );
}

/**
 * Get the default ML backend deployment and create its adapter
 *
 * @returns MLBackendAdapter instance for the default deployment
 * @throws Error if no default deployment configured
 */
export async function getDefaultMLBackendAdapter(): Promise<MLBackendAdapter> {
  const deploymentRepo = new MLBackendDeploymentRepository();
  const defaultDeployment = await deploymentRepo.findDefaultDeployment();

  if (!defaultDeployment) {
    throw new Error(
      "No default ML backend deployment configured. Please configure a default deployment in ml_backend_deployments table."
    );
  }

  return getMLBackendAdapter(defaultDeployment.id);
}

// Re-export types
export type {
  MLBackendAdapter,
  BatchTrainRequest,
  SingleTrainRequest,
  PredictRequest,
} from "./interface";
