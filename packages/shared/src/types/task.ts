/**
 * Task-related type definitions
 */

// Task parameter types
export interface AutoTuneTaskParameter {
  model: string;
  datasetId: number;
  featureColumns: string[];
  targetColumn: string;
  paramGrid?: Record<string, any[]>; // Parameter grid with arrays of values
}

export interface ManualTuneTaskParameter {
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
export interface AutoTuneTaskResult {
  params: Record<string, any>; // Best parameters found
  metrics: Record<string, any>;
  bestScore?: number;
}

export interface ManualTuneTaskResult {
  params: Record<string, any>; // Parameters used
  metrics: Record<string, any>;
}

export interface PredictTaskResult {
  outputFile: string; // Path to prediction output file
  rowCount: number; // Number of predictions made
}

// Specific task types
export interface AutoTuneTask {
  id: number;
  workItemId?: number;
  type: 'auto-tune';
  status: TaskStatus;
  parameter: AutoTuneTaskParameter;
  result?: AutoTuneTaskResult;
  error?: string;
  createdAt?: string;
}

export interface ManualTuneTask {
  id: number;
  workItemId?: number;
  type: 'manual-tune';
  status: TaskStatus;
  parameter: ManualTuneTaskParameter;
  result?: ManualTuneTaskResult;
  error?: string;
  createdAt?: string;
}

export interface PredictTask {
  id: number;
  workItemId?: number;
  type: 'predict';
  status: TaskStatus;
  parameter: PredictTaskParameter;
  result?: PredictTaskResult;
  error?: string;
  createdAt?: string;
}

// Union type for all tasks
export type Task = AutoTuneTask | ManualTuneTask | PredictTask;

// Generic task info (backward compatibility)
export interface TaskInfo {
  id: number;
  workItemId?: number;
  type: string;
  status: string;
  result?: AutoTuneTaskResult | ManualTuneTaskResult | PredictTaskResult | any;
  parameter?:
    | AutoTuneTaskParameter
    | ManualTuneTaskParameter
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

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed';

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
