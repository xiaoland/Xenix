import { db, schema } from '../../database';
import { eq } from 'drizzle-orm';

export default defineEventHandler(async (event) => {
  try {
    const workItemId = getRouterParam(event, 'id');

    if (!workItemId) {
      throw createError({
        statusCode: 400,
        message: 'Work item ID is required',
      });
    }

    const workItems = await db
      .select()
      .from(schema.workItems)
      .where(eq(schema.workItems.workItemId, workItemId))
      .limit(1);

    if (workItems.length === 0) {
      throw createError({
        statusCode: 404,
        message: 'Work item not found',
      });
    }

    const workItem = workItems[0];

    return {
      success: true,
      workItem: {
        ...workItem,
        taskIds: Array.isArray(workItem.taskIds) ? workItem.taskIds : JSON.parse(workItem.taskIds || '[]'),
      },
    };
  } catch (error) {
    console.error('Work item fetch error:', error);
    if (error && typeof error === 'object' && 'statusCode' in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to fetch work item',
    });
  }
});
