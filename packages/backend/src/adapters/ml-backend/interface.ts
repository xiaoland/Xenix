/**
 * ML Backend Adapter Interface
 *
 * Defines the contract for adapters that invoke ml-backend operations.
 * Different adapters handle invocation differently (local spawn, FC invoke, etc.)
 */

export interface MLBackendAdapter {
  /**
   * Execute auto-tune (batch training with GridSearchCV)
   */
  autoTune(options: AutoTuneRequest): Promise<void>;

  /**
   * Execute manual-tune (single training with specific parameters)
   */
  manualTune(options: ManualTuneRequest): Promise<void>;

  /**
   * Execute prediction
   */
  predict(options: PredictRequest): Promise<void>;

  /**
   * Check if the adapter is available/configured
   */
  isAvailable(): boolean;
}

/**
 * Auto-tune request
 */
export interface AutoTuneRequest {
  taskId: number;
  inputFile: string; // Path or OSS key depending on adapter
  model: string;
  featureColumns: string[];
  targetColumn: string;
  paramGrid?: Record<string, any[]>;
}

/**
 * Manual-tune request
 */
export interface ManualTuneRequest {
  taskId: number;
  inputFile: string; // Path or OSS key depending on adapter
  model: string;
  featureColumns: string[];
  targetColumn: string;
  parameters: Record<string, any>;
  parentTaskId?: number;
}

/**
 * Predict request
 */
export interface PredictRequest {
  taskId: number;
  trainingDataPath: string; // Path or OSS key depending on adapter
  predictionData: string | any[]; // Path/key or inline data
  outputPath: string; // Path or OSS key depending on adapter
  model: string;
  params: Record<string, any>;
  featureColumns: string[];
  targetColumn: string;
}
