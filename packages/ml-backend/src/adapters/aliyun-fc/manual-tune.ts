/**
 * Aliyun FC Manual-Tune Adapter
 *
 * Handles manual tuning (single training with specific parameters) requests from Aliyun Function Compute
 */

import { singleTrain } from '../../core/single-train';
import { createLogger } from '../../utils/logger';
import type { SingleTrainOutput } from '../../types';

/**
 * FC Handler for manual-tune operations
 */
export async function handler(event: any, context: any) {
  try {
    // Parse event payload
    const {
      taskId,
      inputFile,
      model,
      featureColumns,
      targetColumn,
      params,
      parentTaskId,
    } = event;

    // Validate required fields
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

    // Create logger (use DATABASE_URL from environment)
    const logger = createLogger(taskId, {
      databaseUrl: process.env.DATABASE_URL || '',
    });

    await logger.log(
      `FC manual-tune started: ${model}`,
      'INFO',
      { requestId: context.requestId }
    );

    // Execute single training
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
      `FC manual-tune completed: ${model}`,
      'INFO',
      { requestId: context.requestId, metrics: result.metrics }
    );

    return {
      statusCode: 200,
      body: JSON.stringify(result),
    };
  } catch (error) {
    console.error('FC manual-tune error:', error);

    return {
      statusCode: 500,
      body: JSON.stringify({
        error: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : undefined,
      }),
    };
  }
}
