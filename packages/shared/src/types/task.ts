/**
 * Task-related type definitions
 */

// Task parameter types
export interface BatchTrainTaskParameter {
  model: string;
  datasetId: number;
  featureColumns: string[];
  targetColumn: string;
  paramGrid?: Record<string, any[]>; // Parameter grid with arrays of values
}

export interface SingleTrainTaskParameter {
  model: string;
  datasetId: number;
  featureColumns: string[];
  targetColumn: string;
  parameters: Record<string, any>; // Single parameter values
}

export interface PredictTaskParameter {
  model: string;
  trainingDatasetId: number;
  predictionDatasetId: number;
  featureColumns: string[];
  targetColumn: string;
  parameters: Record<string, any>; // Model parameters used for prediction
}

// Task result types
export interface BatchTrainTaskResult {
  params: Record<string, any>; // Best parameters found
  metrics: Record<string, any>;
  bestScore?: number;
}

export interface SingleTrainTaskResult {
  params: Record<string, any>; // Parameters used
  metrics: Record<string, any>;
}

export interface PredictTaskResult {
  // For file-based predictions
  predictedDataPath?: string; // Path to prediction output file
  fittedModelPath?: string; // Path to fitted model file

  // For inline predictions
  predictedData?: any[]; // Inline prediction results

  // Legacy field (backward compatibility)
  outputFile?: string; // Path to prediction output file
  rowCount?: number; // Number of predictions made
}

// Specific task types
export interface BatchTrainTask {
  id: number;
  workItemId?: number;
  type: "batch-train";
  status: TaskStatus;
  parameter: BatchTrainTaskParameter;
  result?: BatchTrainTaskResult;
  error?: string;
  createdAt?: string;
}

export interface SingleTrainTask {
  id: number;
  workItemId?: number;
  type: "single-train";
  status: TaskStatus;
  parameter: SingleTrainTaskParameter;
  result?: SingleTrainTaskResult;
  error?: string;
  createdAt?: string;
}

export interface PredictTask {
  id: number;
  workItemId?: number;
  type: "predict";
  status: TaskStatus;
  parameter: PredictTaskParameter;
  result?: PredictTaskResult;
  error?: string;
  createdAt?: string;
}

// Union type for all tasks
export type Task = BatchTrainTask | SingleTrainTask | PredictTask;

// Generic task info (backward compatibility)
export interface TaskInfo {
  id: number;
  workItemId?: number;
  type: string;
  status: string;
  result?: BatchTrainTaskResult | SingleTrainTaskResult | PredictTaskResult | any;
  parameter?:
    | BatchTrainTaskParameter
    | SingleTrainTaskParameter
    | PredictTaskParameter
    | any;
  error?: string;
  createdAt?: string;
}

export interface TaskLog {
  level: string;
  message: string;
  timestamp: string;
}

export type TaskStatus = "pending" | "running" | "completed" | "failed";

/**
 * Prediction task state for UI tracking
 * Used by PredictionStep component to track prediction progress
 */
export interface PredictionTask {
  taskId: number;
  status: TaskStatus;
  outputFile?: string;
  error?: string;
}
