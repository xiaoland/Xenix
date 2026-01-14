/**
 * Aliyun FC Auto-Tune Adapter
 *
 * Handles auto-tuning (batch training with GridSearchCV) requests from Aliyun Function Compute
 */

import { batchTrain } from '../../core/batch-train';
import { createLogger } from '../../utils/logger';
import type { BatchTrainOutput } from '../../types';

/**
 * FC Handler for auto-tune operations
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
      paramGrid,
    } = event;

    // Validate required fields
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

    // Create logger (use DATABASE_URL from environment)
    const logger = createLogger(taskId, {
      databaseUrl: process.env.DATABASE_URL || '',
    });

    await logger.log(
      `FC auto-tune started: ${model}`,
      'INFO',
      { requestId: context.requestId }
    );

    // Execute batch training
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
      `FC auto-tune completed: ${model}`,
      'INFO',
      { requestId: context.requestId, metrics: result.metrics }
    );

    return {
      statusCode: 200,
      body: JSON.stringify(result),
    };
  } catch (error) {
    console.error('FC auto-tune error:', error);

    return {
      statusCode: 500,
      body: JSON.stringify({
        error: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : undefined,
      }),
    };
  }
}
