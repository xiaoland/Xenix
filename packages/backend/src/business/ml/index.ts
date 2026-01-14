/**
 * ML operations wrapper
 * Re-exports ML functions from @xenix/ml-backend with backend-specific context
 */

import path from "path";

import {
  batchTrain as mlBatchTrain,
  singleTrain as mlSingleTrain,
  predict as mlPredict,
  createLogger,
} from "@xenix/ml-backend";

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
  const {
    inputFile,
    model,
    featureColumns,
    targetColumn,
    taskId,
    paramGrid,
  } = options;

  const logger = createLogger(taskId, {
    databaseUrl: process.env.DATABASE_URL!,
    serviceName: "xenix-backend",
  });

  await mlBatchTrain({
    inputFile,
    model,
    featureColumns,
    targetColumn,
    paramGrid: paramGrid || {},
    taskId,
    logger,
  });
}

/**
 * Manual-tune (single training with specific parameters)
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

  const logger = createLogger(taskId, {
    databaseUrl: process.env.DATABASE_URL!,
    serviceName: "xenix-backend",
  });

  await mlSingleTrain({
    inputFile,
    model,
    featureColumns,
    targetColumn,
    params: parameters,
    taskId,
    logger,
    parentTaskId,
  });
}

/**
 * Predict (file-based prediction)
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

  const logger = createLogger(taskId, {
    databaseUrl: process.env.DATABASE_URL!,
    serviceName: "xenix-backend",
  });

  await mlPredict({
    trainData: trainingDataPath,
    predictData: predictionDataPath,
    outputPath,
    model,
    params,
    featureColumns,
    targetColumn,
    taskId,
    logger,
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

  const logger = createLogger(taskId, {
    databaseUrl: process.env.DATABASE_URL!,
    serviceName: "xenix-backend",
  });

  await mlPredict({
    trainData: trainingDataPath,
    predictData: predictionData, // Pass inline array directly
    outputPath,
    model,
    params,
    featureColumns,
    targetColumn,
    taskId,
    logger,
  });
}

/**
 * Get available models by scanning Python modules
 * Uses executePythonSync from ml-backend
 */
export function getAvailableModels(): string[] {
  // For now, return hardcoded list of models
  // This can be enhanced to use scan_models.py from ml-backend
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
