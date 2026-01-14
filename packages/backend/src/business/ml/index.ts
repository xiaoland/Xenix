import path from 'path';

import { executePythonTask } from '../../utils/pythonExecutor';
import {
  AutoTuneOptions,
  ManualTuneOptions,
  PredictFileOptions,
  PredictInlineOptions,
  PredictOptions,
} from './types';

/**
 * Helper function to get ML directory based on environment
 * For FC deployment, scripts are in dist-fc/ml/
 * For local dev, scripts are in src/business/ml/
 */
function getMLDirectory(): string {
  // Check if running in Aliyun FC environment
  if (process.env.NODE_ENV === 'production' && process.env.FC_FUNC_CODE_PATH) {
    // FC environment - scripts are in ml/ subdirectory
    return path.join(process.env.FC_FUNC_CODE_PATH, 'ml');
  }

  // Local development - use src directory
  return path.join(process.cwd(), 'src', 'business', 'ml');
}

// Constants for ML script paths
const ML_MODELS_DIR = getMLDirectory();

/**
 * Helper function to get script path
 */
function getScriptPath(scriptName: string): string {
  return path.join(ML_MODELS_DIR, scriptName);
}

/**
 * Helper function to get working directory
 */
function getWorkingDirectory(): string {
  return ML_MODELS_DIR;
}

/**
 * High-level function to auto-tune a machine learning model
 *
 * @param options - Auto-tuning configuration options
 * @returns Promise that resolves when auto-tuning task is started
 */
export async function autoTune(options: AutoTuneOptions): Promise<void> {
  const { inputFile, model, featureColumns, targetColumn, taskId, paramGrid } =
    options;

  // Prepare stdin data for Python script
  const stdinData = {
    inputFile,
    model: model.toLowerCase(),
    featureColumns,
    targetColumn,
    ...(paramGrid && { paramGrid }), // Include paramGrid if provided
  };

  // Execute Python task with auto_tune_model.py
  await executePythonTask({
    script: getScriptPath('auto_tune_model.py'),
    stdinData,
    taskId,
    cwd: getWorkingDirectory(),
  });
}

/**
 * High-level function to manually tune a machine learning model with specific parameters
 *
 * @param options - Manual tuning configuration options
 * @returns Promise that resolves when manual tuning task is started
 */
export async function manualTune(options: ManualTuneOptions): Promise<void> {
  const {
    inputFile,
    model,
    featureColumns,
    targetColumn,
    taskId,
    parameters,
    parentTaskId,
  } = options;

  // Prepare stdin data for Python script
  const stdinData = {
    inputFile,
    model: model.toLowerCase(),
    featureColumns,
    targetColumn,
    parameters, // Single parameter values
    ...(parentTaskId && { parentTaskId }),
  };

  // Execute Python task with manual_tune_model.py
  await executePythonTask({
    script: getScriptPath('manual_tune_model.py'),
    stdinData,
    taskId,
    cwd: getWorkingDirectory(),
  });
}

/**
 * High-level function to make predictions using a trained model
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
    taskId,
  } = options;

  // Prepare stdin data for Python script
  const stdinData = {
    trainingDataPath,
    predictionDataPath,
    outputPath,
    model: model.toLowerCase(),
    params,
    featureColumns,
    targetColumn,
  };

  // Execute Python task
  await executePythonTask({
    script: getScriptPath('predict.py'),
    stdinData,
    taskId,
    cwd: getWorkingDirectory(),
  });
}

/**
 * High-level function to make predictions using a trained model with file-based input
 *
 * @param options - File-based prediction configuration options
 * @returns Promise that resolves when prediction task is started
 */
export async function predictFile(options: PredictFileOptions): Promise<void> {
  const {
    trainingDataPath,
    predictionDataPath,
    outputPath,
    model,
    params,
    featureColumns,
    targetColumn,
    taskId,
  } = options;

  // Prepare stdin data for Python script
  const stdinData = {
    trainingDataPath,
    predictionDataPath,
    outputPath,
    model: model.toLowerCase(),
    params,
    featureColumns,
    targetColumn,
  };

  // Execute Python task with predict_on_file.py
  await executePythonTask({
    script: getScriptPath('predict_on_file.py'),
    stdinData,
    taskId,
    cwd: getWorkingDirectory(),
  });
}

/**
 * High-level function to make predictions using a trained model with inline JSON data
 *
 * @param options - Inline prediction configuration options
 * @returns Promise that resolves when prediction task is started
 */
export async function predictInline(
  options: PredictInlineOptions
): Promise<void> {
  const {
    trainingDataPath,
    predictionData,
    outputPath,
    model,
    params,
    featureColumns,
    targetColumn,
    taskId,
  } = options;

  // Prepare stdin data for Python script
  const stdinData = {
    trainingDataPath,
    predictionData,
    outputPath,
    model: model.toLowerCase(),
    params,
    featureColumns,
    targetColumn,
  };

  // Execute Python task with predict_on_json.py
  await executePythonTask({
    script: getScriptPath('predict_on_json.py'),
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
    'regression.linear_regression_hyperparameter_tuning',
    'regression.ridge',
    'regression.lasso',
    'regression.bayesian_ridge_regression',
    'regression.k_nearest_neighbors',
    'regression.regression_decision_tree',
    'regression.random_forest',
    'regression.gbdt',
    'regression.adaboost',
    'regression.xgboost',
    'regression.lightgbm',
    'regression.polynomial_regression',
  ];
}
