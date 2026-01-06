/**
 * ML Task Job Processor
 * Handles ML tasks (auto-tune, manual-tune, predict) in background
 */

import { Job } from 'bullmq';
import { autoTune, manualTune, predictInline } from '../business/ml/index.js';
import { TaskRepository } from '../repositories/index.js';
import logger from '../utils/logger/index.js';

const taskRepo = new TaskRepository();

export interface MLTaskData {
  type: 'auto-tune' | 'manual-tune' | 'predict-inline';
  taskId: number;
  params: any;
}

export async function processMLTask(job: Job<MLTaskData>) {
  const { type, taskId, params } = job.data;

  logger.info({ jobId: job.id, taskId, type }, 'Processing ML task');

  try {
    // Mark task as running
    await taskRepo.markAsRunning(taskId);

    let result;

    switch (type) {
      case 'auto-tune':
        result = await autoTune({
          inputFile: params.inputFile,
          model: params.model,
          featureColumns: params.featureColumns,
          targetColumn: params.targetColumn,
          taskId,
          paramGrid: params.paramGrid,
        });
        break;

      case 'manual-tune':
        result = await manualTune({
          inputFile: params.inputFile,
          model: params.model,
          featureColumns: params.featureColumns,
          targetColumn: params.targetColumn,
          taskId,
          parameters: params.parameters,
        });
        break;

      case 'predict-inline':
        result = await predictInline({
          trainingDataPath: params.trainingDataPath,
          predictionData: params.predictionData,
          outputPath: params.outputPath,
          model: params.model,
          params: params.params,
          featureColumns: params.featureColumns,
          targetColumn: params.targetColumn,
          taskId,
        });
        break;

      default:
        throw new Error(`Unknown task type: ${type}`);
    }

    logger.info({ jobId: job.id, taskId, type }, 'ML task completed');
    return result;
  } catch (error) {
    logger.error({ jobId: job.id, taskId, type, error }, 'ML task failed');
    
    // Update task status to failed
    await taskRepo.updateStatus(
      taskId,
      'failed',
      undefined,
      error instanceof Error ? error.message : 'Unknown error'
    );

    throw error;
  }
}
