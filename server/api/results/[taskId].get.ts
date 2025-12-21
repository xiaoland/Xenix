import { db, schema } from '../../database';
import { eq } from 'drizzle-orm';

export default defineEventHandler(async (event) => {
  try {
    const taskId = getRouterParam(event, 'taskId');

    if (!taskId) {
      throw createError({
        statusCode: 400,
        message: 'Task ID is required',
      });
    }

    // Fetch model results for this task
    const results = await db
      .select()
      .from(schema.modelResults)
      .where(eq(schema.modelResults.taskId, taskId));

    if (results.length === 0) {
      return {
        success: true,
        results: null,
      };
    }

    return {
      success: true,
      results: results[0], // Return first result (should only be one per task)
    };
  } catch (error) {
    console.error('Results fetch error:', error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to fetch results',
    });
  }
});
