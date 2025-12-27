import { db, schema } from '../../../database';
import { eq } from 'drizzle-orm';

/**
 * API endpoint to fetch all training history for a specific model
 * Includes both auto-tune results and manual training results with task status
 */
export default defineEventHandler(async (event) => {
  try {
    const model = getRouterParam(event, 'model');

    if (!model) {
      throw createError({
        statusCode: 400,
        message: 'Model name is required',
      });
    }

    // Fetch all results for this model with task status, ordered by creation time
    const results = await db
      .select({
        id: schema.modelResults.id,
        taskId: schema.modelResults.taskId,
        model: schema.modelResults.model,
        params: schema.modelResults.params,
        parentTaskId: schema.modelResults.parentTaskId,
        trainingType: schema.modelResults.trainingType,
        mse_train: schema.modelResults.mse_train,
        mae_train: schema.modelResults.mae_train,
        r2_train: schema.modelResults.r2_train,
        mse_test: schema.modelResults.mse_test,
        mae_test: schema.modelResults.mae_test,
        r2_test: schema.modelResults.r2_test,
        createdAt: schema.modelResults.createdAt,
        status: schema.tasks.status,
      })
      .from(schema.modelResults)
      .leftJoin(schema.tasks, eq(schema.modelResults.taskId, schema.tasks.taskId))
      .where(eq(schema.modelResults.model, model))
      .orderBy(schema.modelResults.createdAt)
      .all();

    return {
      success: true,
      results,
      count: results.length,
    };
  } catch (error) {
    console.error('Training history fetch error:', error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to fetch training history',
    });
  }
});
