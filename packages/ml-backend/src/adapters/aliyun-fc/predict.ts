/**
 * Aliyun FC Predict Adapter
 *
 * Handles prediction requests from Aliyun Function Compute
 */

import { predict } from '../../core/predict';
import { createLogger } from '../../utils/logger';
import type { PredictOutput } from '../../types';

/**
 * FC Handler for predict operations
 */
export async function handler(event: any, context: any) {
  try {
    // Parse event payload
    const {
      taskId,
      trainData,
      predictData,
      outputPath,
      model,
      params,
      featureColumns,
      targetColumn,
    } = event;

    // Validate required fields
    if (
      !taskId ||
      !trainData ||
      !predictData ||
      !outputPath ||
      !model ||
      !params ||
      !featureColumns ||
      !targetColumn
    ) {
      throw new Error('Missing required fields in event payload');
    }

    // Create logger (use DATABASE_URL from environment)
    const logger = createLogger(taskId, {
      databaseUrl: process.env.DATABASE_URL || '',
    });

    await logger.log(
      `FC predict started: ${model}`,
      'INFO',
      { requestId: context.requestId }
    );

    // Execute prediction
    const result: PredictOutput = await predict({
      trainData,
      predictData,
      outputPath,
      model,
      params,
      featureColumns,
      targetColumn,
      taskId,
      logger,
    });

    await logger.log(
      `FC predict completed: ${model}`,
      'INFO',
      { requestId: context.requestId }
    );

    return {
      statusCode: 200,
      body: JSON.stringify(result),
    };
  } catch (error) {
    console.error('FC predict error:', error);

    return {
      statusCode: 500,
      body: JSON.stringify({
        error: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : undefined,
      }),
    };
  }
}
