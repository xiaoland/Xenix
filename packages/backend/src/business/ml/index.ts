/**
 * ML operations
 * Uses ML Backend HTTP service to invoke operations
 */

import { MLBackendDeploymentRepository } from '../../repositories/MLBackendDeploymentRepository';
import { getMLBackendService } from '../../services/MLBackendService';
import type {
  BatchTrainOptions,
  SingleTrainOptions,
  PredictOptions,
  PredictInlineOptions,
  PredictFileOptions,
} from './types';

/**
 * Get deployment (either specified or default)
 */
async function getDeployment(deploymentId?: number) {
  const deploymentRepo = new MLBackendDeploymentRepository();

  if (deploymentId) {
    const deployment = await deploymentRepo.findById(deploymentId);
    if (!deployment) {
      throw new Error(`Deployment ${deploymentId} not found`);
    }
    if (!deployment.is_active) {
      throw new Error(`Deployment ${deploymentId} is inactive`);
    }
    return deployment;
  }

  const defaultDeployment = await deploymentRepo.findDefaultDeployment();
  if (!defaultDeployment) {
    throw new Error('No default ML backend deployment configured');
  }

  return defaultDeployment;
}

export async function batchTrain(options: BatchTrainOptions): Promise<void> {
  const deployment = await getDeployment(options.deploymentId);
  const mlService = getMLBackendService();

  await mlService.execute(deployment, {
    operation: 'batch-train',
    data: {
      task_id: options.taskId,
      input_file: options.inputFile,
      model: options.model,
      feature_columns: options.featureColumns,
      target_column: options.targetColumn,
      param_grid: options.paramGrid || {},
    },
  });
}

export async function singleTrain(options: SingleTrainOptions): Promise<void> {
  const deployment = await getDeployment(options.deploymentId);
  const mlService = getMLBackendService();

  await mlService.execute(deployment, {
    operation: 'single-train',
    data: {
      task_id: options.taskId,
      input_file: options.inputFile,
      model: options.model,
      feature_columns: options.featureColumns,
      target_column: options.targetColumn,
      parameters: options.parameters,
      parent_task_id: options.parentTaskId,
    },
  });
}

export async function predict(options: PredictOptions): Promise<void> {
  const deployment = await getDeployment(options.deploymentId);
  const mlService = getMLBackendService();

  await mlService.execute(deployment, {
    operation: 'predict',
    data: {
      task_id: options.taskId,
      training_data_path: options.trainingDataPath,
      prediction_data_path: options.predictionDataPath,
      output_path: options.outputPath,
      model: options.model,
      parameters: options.params,
      feature_columns: options.featureColumns,
      target_column: options.targetColumn,
    },
  });
}

export async function predictFile(
  options: PredictFileOptions,
): Promise<void> {
  return predict(options as PredictOptions);
}

export async function predictInline(
  options: PredictInlineOptions,
): Promise<void> {
  const deployment = await getDeployment(options.deploymentId);
  const mlService = getMLBackendService();

  await mlService.execute(deployment, {
    operation: 'predict',
    data: {
      task_id: options.taskId,
      training_data_path: options.trainingDataPath,
      prediction_data: options.predictionData,
      output_path: options.outputPath,
      model: options.model,
      parameters: options.params,
      feature_columns: options.featureColumns,
      target_column: options.targetColumn,
    },
  });
}

export function getAvailableModels(): string[] {
  return [
    'regression.ridge',
    'regression.lasso',
    'regression.linear_regression_hyperparameter_tuning',
    'regression.polynomial_regression',
    'regression.k_nearest_neighbors',
    'regression.regression_decision_tree',
    'regression.random_forest',
    'regression.adaboost',
    'regression.gbdt',
    'regression.xgboost',
    'regression.lightgbm',
    'regression.bayesian_ridge_regression',
  ];
}
