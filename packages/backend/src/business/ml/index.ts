/**
 * ML operations
 * Uses ML Backend adapters to invoke operations (local spawn or FC invoke)
 */

import {
  getMLBackendAdapter,
  getDefaultMLBackendAdapter,
} from "../../adapters/ml-backend";
import type {
  BatchTrainOptions,
  SingleTrainOptions,
  PredictOptions,
  PredictInlineOptions,
  PredictFileOptions,
} from "./types";

export async function batchTrain(options: BatchTrainOptions): Promise<void> {
  const adapter = options.deploymentId
    ? await getMLBackendAdapter(options.deploymentId)
    : await getDefaultMLBackendAdapter();

  await adapter.batchTrain({
    taskId: options.taskId,
    inputFile: options.inputFile,
    model: options.model,
    featureColumns: options.featureColumns,
    targetColumn: options.targetColumn,
    paramGrid: options.paramGrid,
  });
}

export async function singleTrain(options: SingleTrainOptions): Promise<void> {
  const adapter = options.deploymentId
    ? await getMLBackendAdapter(options.deploymentId)
    : await getDefaultMLBackendAdapter();

  await adapter.singleTrain({
    taskId: options.taskId,
    inputFile: options.inputFile,
    model: options.model,
    featureColumns: options.featureColumns,
    targetColumn: options.targetColumn,
    parameters: options.parameters,
    parentTaskId: options.parentTaskId,
  });
}

export async function predict(options: PredictOptions): Promise<void> {
  const adapter = options.deploymentId
    ? await getMLBackendAdapter(options.deploymentId)
    : await getDefaultMLBackendAdapter();

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

export async function predictFile(
  options: PredictFileOptions
): Promise<void> {
  return predict(options as PredictOptions);
}

export async function predictInline(
  options: PredictInlineOptions
): Promise<void> {
  const adapter = options.deploymentId
    ? await getMLBackendAdapter(options.deploymentId)
    : await getDefaultMLBackendAdapter();

  await adapter.predict({
    taskId: options.taskId,
    trainingDataPath: options.trainingDataPath,
    predictionData: options.predictionData,
    outputPath: options.outputPath,
    model: options.model,
    params: options.params,
    featureColumns: options.featureColumns,
    targetColumn: options.targetColumn,
  });
}

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
