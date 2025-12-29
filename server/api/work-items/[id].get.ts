import { db, schema } from '../../database';
import { eq } from 'drizzle-orm';

export default defineEventHandler(async (event) => {
  try {
    const id = Number(getRouterParam(event, 'id'));

    if (isNaN(id)) {
      throw createError({
        statusCode: 400,
        message: 'Invalid work item ID',
      });
    }

    const workItems = await db
      .select()
      .from(schema.workItems)
      .where(eq(schema.workItems.id, id))
      .limit(1);

    if (workItems.length === 0) {
      throw createError({
        statusCode: 404,
        message: 'Work item not found',
      });
    }

    const workItem = workItems[0];

    // Fetch related tasks
    const tasks = await db
      .select()
      .from(schema.tasks)
      .where(eq(schema.tasks.workItemId, id));

    return {
      success: true,
      workItem: {
        ...workItem,
        tasks,
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
