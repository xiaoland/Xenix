/**
 * ML operations
 * Uses ML Backend adapters to invoke operations (local spawn or FC invoke)
 */

import { getMLBackendAdapter } from "../../adapters/ml-backend";
import type {
  AutoTuneOptions,
  ManualTuneOptions,
  PredictOptions,
  PredictInlineOptions,
  PredictFileOptions,
} from "./types";

/**
 * Auto-tune (batch training with GridSearchCV)
 */
export async function autoTune(options: AutoTuneOptions): Promise<void> {
  const adapter = getMLBackendAdapter();

  await adapter.autoTune({
    taskId: options.taskId,
    inputFile: options.inputFile,
    model: options.model,
    featureColumns: options.featureColumns,
    targetColumn: options.targetColumn,
    paramGrid: options.paramGrid,
  });
}

/**
 * Manual-tune (single training with specific parameters)
 */
export async function manualTune(options: ManualTuneOptions): Promise<void> {
  const adapter = getMLBackendAdapter();

  await adapter.manualTune({
    taskId: options.taskId,
    inputFile: options.inputFile,
    model: options.model,
    featureColumns: options.featureColumns,
    targetColumn: options.targetColumn,
    parameters: options.parameters,
    parentTaskId: options.parentTaskId,
  });
}

/**
 * Predict (file-based prediction)
 */
export async function predict(options: PredictOptions): Promise<void> {
  const adapter = getMLBackendAdapter();

  await adapter.predict({
    taskId: options.taskId,
    trainingDataPath: options.trainingDataPath,
    predictionData: options.predictionDataPath,
    outputPath: options.outputPath,
    model: options.model,
    params: options.params,
    featureColumns: options.featureColumns,
    targetColumn: options.targetColumn,
  });
}

/**
 * Predict with file (alias for predict)
 */
export async function predictFile(
  options: PredictFileOptions
): Promise<void> {
  return predict(options as PredictOptions);
}

/**
 * Predict with inline JSON data
 */
export async function predictInline(
  options: PredictInlineOptions
): Promise<void> {
  const adapter = getMLBackendAdapter();

  await adapter.predict({
    taskId: options.taskId,
    trainingDataPath: options.trainingDataPath,
    predictionData: options.predictionData, // Pass inline array directly
    outputPath: options.outputPath,
    model: options.model,
    params: options.params,
    featureColumns: options.featureColumns,
    targetColumn: options.targetColumn,
  });
}

/**
 * Get available models
 */
export function getAvailableModels(): string[] {
  return [
    "regression.ridge",
    "regression.lasso",
    "regression.linear_regression_hyperparameter_tuning",
    "regression.polynomial_regression",
    "regression.k_nearest_neighbors",
    "regression.regression_decision_tree",
    "regression.random_forest",
    "regression.adaboost",
    "regression.gbdt",
    "regression.xgboost",
    "regression.lightgbm",
    "regression.bayesian_ridge_regression",
  ];
}
