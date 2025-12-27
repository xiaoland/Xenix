import { db, schema } from '../../database';
import { eq } from 'drizzle-orm';

export default defineEventHandler(async (event) => {
  try {
    const id = getRouterParam(event, 'id');

    if (!id) {
      throw createError({
        statusCode: 400,
        message: 'Task ID is required',
      });
    }

    const taskId = parseInt(id);

    // Fetch task with results
    const [task] = await db
      .select()
      .from(schema.tasks)
      .where(eq(schema.tasks.id, taskId))
      .limit(1);

    if (!task) {
      return {
        success: true,
        results: null,
      };
    }

    // Return task result field
    return {
      success: true,
      results: task.result || null,
    };
  } catch (error) {
    console.error('Results fetch error:', error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to fetch results',
    });
  }
});
