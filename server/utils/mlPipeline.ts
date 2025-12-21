import path from 'path';
import { executePythonTask } from './pythonExecutor';

// Constants for ML script paths
const ML_MODELS_DIR = path.join('app', 'models', 'regression');

/**
 * Helper function to get script path
 */
function getScriptPath(scriptName: string): string {
  return path.join(process.cwd(), ML_MODELS_DIR, scriptName);
}

/**
 * Helper function to get working directory
 */
function getWorkingDirectory(): string {
  return path.join(process.cwd(), ML_MODELS_DIR);
}

/**
 * Options for hyperparameter tuning
 */
export interface TuneOptions {
  inputFile: string;
  model: string;
  featureColumns: string[];
  targetColumn: string;
  taskId: string;
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
  taskId: string;
}

/**
 * High-level function to tune a machine learning model
 * Supports both local and Docker execution modes based on PYTHON_EXECUTION_MODE env var
 * 
 * @param options - Tuning configuration options
 * @returns Promise that resolves when tuning task is started
 */
export async function tune(options: TuneOptions): Promise<void> {
  const { inputFile, model, featureColumns, targetColumn, taskId } = options;

  // Prepare stdin data for Python script
  const stdinData = {
    inputFile,
    model,
    featureColumns,
    targetColumn
  };
  
  // Execute Python task (mode is determined automatically by pythonExecutor)
  await executePythonTask({
    script: getScriptPath('tune_model.py'),
    stdinData,
    taskId,
    cwd: getWorkingDirectory(),
  });
}

/**
 * High-level function to make predictions using a trained model
 * Supports both local and Docker execution modes based on PYTHON_EXECUTION_MODE env var
 * 
 * @param options - Prediction configuration options
 * @returns Promise that resolves when prediction task is started
 */
export async function predict(options: PredictOptions): Promise<void> {
  const {
    trainingDataPath,
    predictionDataPath,
    outputPath,
    model,
    params,
    featureColumns,
    targetColumn,
    taskId
  } = options;

  // Prepare stdin data for Python script
  const stdinData = {
    trainingDataPath,
    predictionDataPath,
    outputPath,
    model,
    params,
    featureColumns,
    targetColumn
  };
  
  // Execute Python task (mode is determined automatically by pythonExecutor)
  await executePythonTask({
    script: getScriptPath('predict.py'),
    stdinData,
    taskId,
    cwd: getWorkingDirectory(),
  });
}

/**
 * Get available ML models
 */
export function getAvailableModels(): string[] {
  return [
    'Linear_Regression_Hyperparameter_Tuning',
    'Ridge',
    'Lasso',
    'Bayesian_Ridge_Regression',
    'K-Nearest_Neighbors',
    'Regression_Decision_Tree',
    'Random_Forest',
    'GBDT',
    'AdaBoost',
    'XGBoost',
    'LightGBM',
    'Polynomial_Regression'
  ];
}

// Re-export getExecutionMode from pythonExecutor for convenience
export { getExecutionMode } from './pythonExecutor';
