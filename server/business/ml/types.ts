export interface TuneOptions {
  inputFile: string;
  model: string;
  featureColumns: string[];
  targetColumn: string;
  taskId: number; // Changed from string to number
  paramGrid?: Record<string, any>;
  trainingType?: string; // 'auto' or 'manual'
  parentTaskId?: number; // Changed from string to number
}

/**
 * Options for auto-tuning with parameter grid
 */
export interface AutoTuneOptions {
  inputFile: string;
  model: string;
  featureColumns: string[];
  targetColumn: string;
  taskId: number;
  paramGrid?: Record<string, any[]>; // Grid with arrays of values
}

/**
 * Options for manual tuning with specific parameters
 */
export interface ManualTuneOptions {
  inputFile: string;
  model: string;
  featureColumns: string[];
  targetColumn: string;
  taskId: number;
  parameters: Record<string, any>; // Single parameter values
  parentTaskId?: number;
}

/**
 * Options for training with specific parameters
 */
export interface TrainOptions {
  inputFile: string;
  model: string;
  featureColumns: string[];
  targetColumn: string;
  taskId: number;
  parameters: Record<string, any>;
}

/**
 * Options for prediction
 */
export interface PredictOptions {
  trainingDataPath: string;
  predictionDataPath: string;
  outputPath: string;
  model: string;
  params: Record<string, any>;
  featureColumns: string[];
  targetColumn: string;
  taskId: number; // Changed from string to number
}

/**
 * Options for file-based prediction
 */
export interface PredictFileOptions {
  trainingDataPath: string;
  predictionDataPath: string;
  outputPath: string;
  model: string;
  params: Record<string, any>;
  featureColumns: string[];
  targetColumn: string;
  taskId: number;
}

/**
 * Options for inline prediction with JSON data
 */
export interface PredictInlineOptions {
  trainingDataPath: string;
  predictionData: any[];
  model: string;
  params: Record<string, any>;
  featureColumns: string[];
  targetColumn: string;
  taskId: number;
}
