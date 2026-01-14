/**
 * ML Backend Adapter Factory
 *
 * Creates the appropriate adapter based on environment and configuration.
 * Adapters determine how to invoke ml-backend operations (local spawn vs FC invoke).
 */

import { config } from "../../config";
import logger from "../../utils/logger";
import { AliyunFCAdapter } from "./aliyun-fc-adapter";
import type { MLBackendAdapter } from "./interface";
import { SpawnAdapter } from "./spawn-adapter";

/**
 * Create ML Backend adapter based on environment
 *
 * Priority:
 * 1. AliyunFCAdapter - if FC is configured and available (production)
 * 2. SpawnAdapter - fallback for local development
 */
export function createMLBackendAdapter(): MLBackendAdapter {
  // Try FC adapter first (production)
  const fcAdapter = new AliyunFCAdapter();
  if (fcAdapter.isAvailable()) {
    logger.info("Using AliyunFCAdapter for ML operations");
    return fcAdapter;
  }

  // Fallback to spawn adapter (local development)
  logger.info("Using SpawnAdapter for ML operations");
  return new SpawnAdapter();
}

/**
 * Singleton adapter instance
 */
let adapterInstance: MLBackendAdapter | null = null;

/**
 * Get the ML Backend adapter instance
 */
export function getMLBackendAdapter(): MLBackendAdapter {
  if (!adapterInstance) {
    adapterInstance = createMLBackendAdapter();
  }
  return adapterInstance;
}

// Re-export types
export type {
  MLBackendAdapter,
  AutoTuneRequest,
  ManualTuneRequest,
  PredictRequest,
} from "./interface";
