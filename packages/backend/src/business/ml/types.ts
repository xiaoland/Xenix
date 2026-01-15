export interface BatchTrainOptions {
  inputFile: string;
  model: string;
  featureColumns: string[];
  targetColumn: string;
  taskId: number;
  paramGrid?: Record<string, any[]>;
}

export interface SingleTrainOptions {
  inputFile: string;
  model: string;
  featureColumns: string[];
  targetColumn: string;
  taskId: number;
  parameters: Record<string, any>;
  parentTaskId?: number;
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
}
