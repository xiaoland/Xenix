export interface BatchTrainOptions {
  inputFile: string;
  model: string;
  featureColumns: string[];
  targetColumn: string;
  taskId: number;
  paramGrid?: Record<string, any[]>;
  deploymentId?: number; // Optional ML backend deployment ID (uses default if not specified)
}

export interface SingleTrainOptions {
  inputFile: string;
  model: string;
  featureColumns: string[];
  targetColumn: string;
  taskId: number;
  parameters: Record<string, any>;
  parentTaskId?: number;
  deploymentId?: number; // Optional ML backend deployment ID (uses default if not specified)
}

export interface PredictOptions {
  trainingDataPath: string;
  predictionDataPath: string;
  outputPath: string;
  model: string;
  params: Record<string, any>;
  featureColumns: string[];
  targetColumn: string;
  taskId: number;
  deploymentId?: number; // Optional ML backend deployment ID (uses default if not specified)
}

export interface PredictFileOptions {
  trainingDataPath: string;
  predictionDataPath: string;
  outputPath: string;
  model: string;
  params: Record<string, any>;
  featureColumns: string[];
  targetColumn: string;
  taskId: number;
  deploymentId?: number; // Optional ML backend deployment ID (uses default if not specified)
}

export interface PredictInlineOptions {
  trainingDataPath: string;
  predictionData: any[];
  outputPath: string;
  model: string;
  params: Record<string, any>;
  featureColumns: string[];
  targetColumn: string;
  taskId: number;
  deploymentId?: number; // Optional ML backend deployment ID (uses default if not specified)
}
