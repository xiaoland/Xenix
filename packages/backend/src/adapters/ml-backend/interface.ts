/**
 * ML Backend Adapter Interface
 */

export interface MLBackendAdapter {
  batchTrain(options: BatchTrainRequest): Promise<void>;
  singleTrain(options: SingleTrainRequest): Promise<void>;
  predict(options: PredictRequest): Promise<void>;
  isAvailable(): boolean;
}

export interface BatchTrainRequest {
  taskId: number;
  inputFile: string;
  model: string;
  featureColumns: string[];
  targetColumn: string;
  paramGrid?: Record<string, any[]>;
}

export interface SingleTrainRequest {
  taskId: number;
  inputFile: string;
  model: string;
  featureColumns: string[];
  targetColumn: string;
  parameters: Record<string, any>;
  parentTaskId?: number;
}

export interface PredictRequest {
  taskId: number;
  trainingDataPath: string;
  predictionData: string | any[];
  outputPath: string;
  model: string;
  params: Record<string, any>;
  featureColumns: string[];
  targetColumn: string;
}
