/**
 * Aliyun FC Batch Train Adapter
 * Handles batch training (GridSearchCV) requests from Aliyun Function Compute
 */

import { batchTrain } from '../../core/batch-train';
import { createLogger } from '../../utils/logger';
import type { BatchTrainOutput } from '../../types';

export async function handler(event: any, context: any) {
  try {
    const {
      taskId,
      inputFile,
      model,
      featureColumns,
      targetColumn,
      paramGrid,
    } = event;

    if (
      !taskId ||
      !inputFile ||
      !model ||
      !featureColumns ||
      !targetColumn ||
      !paramGrid
    ) {
      throw new Error('Missing required fields in event payload');
    }

    const logger = createLogger(taskId, {
      databaseUrl: process.env.DATABASE_URL || '',
    });

    await logger.log(
      `FC batch-train started: ${model}`,
      'INFO',
      { requestId: context.requestId }
    );

    const result: BatchTrainOutput = await batchTrain({
      inputFile,
      model,
      featureColumns,
      targetColumn,
      paramGrid,
      taskId,
      logger,
    });

    await logger.log(
      `FC batch-train completed: ${model}`,
      'INFO',
      { requestId: context.requestId, metrics: result.metrics }
    );

    return {
      statusCode: 200,
      body: JSON.stringify(result),
    };
  } catch (error) {
    console.error('FC batch-train error:', error);

    return {
      statusCode: 500,
      body: JSON.stringify({
        error: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : undefined,
      }),
    };
  }
}
