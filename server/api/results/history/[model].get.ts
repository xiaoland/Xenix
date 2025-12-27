import { db, schema } from '../../../database';
import { eq, and, or } from 'drizzle-orm';

/**
 * API endpoint to fetch all training history for a specific model
 * Queries tasks table where type is 'auto-tune' or 'train' and parameter.model matches
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

    // Fetch all training tasks for this model, ordered by creation time
    const tasks = await db
      .select()
      .from(schema.tasks)
      .where(
        and(
          or(
            eq(schema.tasks.type, 'auto-tune'),
            eq(schema.tasks.type, 'train')
          )
        )
      )
      .orderBy(schema.tasks.createdAt)
      .all();

    // Filter by model in parameter field and format results
    const results = tasks
      .filter((task) => {
        const param: any = task.parameter || {};
        return param.model === model;
      })
      .map((task) => {
        const param: any = task.parameter || {};
        const result: any = task.result || {};
        
        return {
          id: task.id,
          taskId: task.id, // For backward compatibility
          model: param.model,
          params: result.params,
          parentTaskId: param.parentTaskId,
          trainingType: param.trainingType || 'auto',
          mse_train: result.metrics?.mse_train,
          mae_train: result.metrics?.mae_train,
          r2_train: result.metrics?.r2_train,
          mse_test: result.metrics?.mse_test,
          mae_test: result.metrics?.mae_test,
          r2_test: result.metrics?.r2_test,
          createdAt: task.createdAt,
          status: task.status,
        };
      });

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
