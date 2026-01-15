/**
 * Aliyun FC Single Train Adapter
 * Handles single training (specific parameters) requests from Aliyun Function Compute
 */

import { singleTrain } from '../../core/single-train';
import { createLogger } from '../../utils/logger';
import type { SingleTrainOutput } from '../../types';

export async function handler(event: any, context: any) {
  try {
    const {
      taskId,
      inputFile,
      model,
      featureColumns,
      targetColumn,
      params,
      parentTaskId,
    } = event;

    if (
      !taskId ||
      !inputFile ||
      !model ||
      !featureColumns ||
      !targetColumn ||
      !params
    ) {
      throw new Error('Missing required fields in event payload');
    }

    const logger = createLogger(taskId, {
      databaseUrl: process.env.DATABASE_URL || '',
    });

    await logger.log(
      `FC single-train started: ${model}`,
      'INFO',
      { requestId: context.requestId }
    );

    const result: SingleTrainOutput = await singleTrain({
      inputFile,
      model,
      featureColumns,
      targetColumn,
      params,
      taskId,
      logger,
      parentTaskId,
    });

    await logger.log(
      `FC single-train completed: ${model}`,
      'INFO',
      { requestId: context.requestId, metrics: result.metrics }
    );

    return {
      statusCode: 200,
      body: JSON.stringify(result),
    };
  } catch (error) {
    console.error('FC single-train error:', error);

    return {
      statusCode: 500,
      body: JSON.stringify({
        error: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : undefined,
      }),
    };
  }
}
