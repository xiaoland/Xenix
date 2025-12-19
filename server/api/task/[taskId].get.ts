import { db, schema } from '../../database';
import { eq } from 'drizzle-orm';

export default defineEventHandler(async (event) => {
  const taskId = getRouterParam(event, 'taskId');

  if (!taskId) {
    throw createError({
      statusCode: 400,
      message: 'Task ID is required',
    });
  }

  try {
    // Get task status
    const [task] = await db.select()
      .from(schema.tasks)
      .where(eq(schema.tasks.taskId, taskId))
      .limit(1);

    if (!task) {
      throw createError({
        statusCode: 404,
        message: 'Task not found',
      });
    }

    // Get results based on task type
    let results = null;
    if (task.status === 'completed') {
      if (task.type === 'tuning') {
        const modelResults = await db.select()
          .from(schema.modelResults)
          .where(eq(schema.modelResults.taskId, taskId));
        results = modelResults[0] || null;
      } else if (task.type === 'comparison') {
        const comparisonResults = await db.select()
          .from(schema.comparisonResults)
          .where(eq(schema.comparisonResults.taskId, taskId));
        results = comparisonResults[0] || null;
      }
    }

    return {
      success: true,
      task: {
        taskId: task.taskId,
        type: task.type,
        status: task.status,
        model: task.model,
        error: task.error,
        createdAt: task.createdAt,
        updatedAt: task.updatedAt,
      },
      results,
    };
  } catch (error) {
    console.error('Status check error:', error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to check task status',
    });
  }
});
