import { eq } from 'drizzle-orm';
import path from 'path';

import { zValidator } from '@hono/zod-validator';
import { Hono } from 'hono';

import { InlinePredictSchema } from '@xenix/shared';

import { predictInline } from '../business/ml/index.js';
import { db, schema } from '../database/index.js';
import { BadRequestError, NotFoundError } from '../errors/index.js';
import { authMiddleware } from '../middleware/auth.js';
import logger from '../utils/logger/index.js';

const predict = new Hono()
  .use('*', authMiddleware)

  // Inline prediction (JSON data)
  .post('/inline', zValidator('json', InlinePredictSchema), async (c) => {
    const { predictionData, model, tuningTaskId, workItemId } =
      c.req.valid('json');

    // Load work item to get datasetId (training), featureColumns, targetColumn
    const [workItem] = await db
      .select()
      .from(schema.workItems)
      .where(eq(schema.workItems.id, workItemId))
      .limit(1);

    if (!workItem) {
      throw new NotFoundError('Work item');
    }

    if (!workItem.datasetId) {
      throw new BadRequestError('Work item does not have a training dataset');
    }

    if (!workItem.featureColumns || !workItem.targetColumn) {
      throw new BadRequestError(
        'Work item does not have feature columns or target column configured'
      );
    }

    const featureColumns = workItem.featureColumns as string[];
    const targetColumn = workItem.targetColumn as string;

    // Validate each item in predictionData has all required feature columns
    for (let i = 0; i < predictionData.length; i++) {
      const item = predictionData[i];
      for (const col of featureColumns) {
        if (!(col in item)) {
          throw new BadRequestError(
            `Item at index ${i} is missing required feature column: ${col}`
          );
        }
      }
    }

    // Load training dataset to get trainingDataPath
    const [trainingDataset] = await db
      .select()
      .from(schema.datasets)
      .where(eq(schema.datasets.id, workItem.datasetId))
      .limit(1);

    if (!trainingDataset) {
      throw new NotFoundError('Training dataset');
    }

    const trainingDataPath = trainingDataset.filePath;

    // Load tuning task to get params (result.params)
    const [tuningTask] = await db
      .select()
      .from(schema.tasks)
      .where(eq(schema.tasks.id, tuningTaskId))
      .limit(1);

    if (!tuningTask || !tuningTask.result) {
      throw new NotFoundError('Tuning results for the specified task ID');
    }

    const result: any = tuningTask.result;
    const params = result.params;

    // Create task record first to get taskId
    const [insertedTask] = await db
      .insert(schema.tasks)
      .values({
        workItemId,
        type: 'predict',
        status: 'pending',
        parameter: {
          model,
          trainingDatasetId: workItem.datasetId,
          featureColumns,
          targetColumn,
          tuningTaskId,
          predictionType: 'inline',
          predictionDataCount: predictionData.length,
        },
      })
      .returning();

    const taskId = insertedTask.id;

    // Generate output file path with taskId
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const outputFile = path.join(
      process.cwd(),
      'uploads',
      `inline_prediction_${workItemId}_${taskId}_${timestamp}.xlsx`
    );

    // Update task with outputFile
    await db
      .update(schema.tasks)
      .set({
        parameter: {
          ...(insertedTask.parameter as any),
          outputFile,
        },
      })
      .where(eq(schema.tasks.id, taskId));

    // Call predictInline() in background with setImmediate
    setImmediate(() => {
      predictInline({
        trainingDataPath,
        predictionData,
        outputPath: outputFile,
        model,
        params,
        featureColumns,
        targetColumn,
        taskId,
      }).catch((error) => {
        logger.error(
          { error, taskId },
          `Failed to execute inline prediction task`
        );
      });
    });

    return c.json(
      {
        taskId,
        message: 'Inline prediction started',
      },
      201
    );
  });

// TODO: by-file and generic predict endpoints
// These are complex and require file upload handling similar to datasets

export default predict;
