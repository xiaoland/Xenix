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

    // Delete work item (cascades to tasks due to FK if configured)
    await db
      .delete(schema.workItems)
      .where(eq(schema.workItems.id, id));

    return {
      success: true,
      message: 'Work item deleted successfully',
    };
  } catch (error) {
    console.error('Work item deletion error:', error);
    if (error && typeof error === 'object' && 'statusCode' in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to delete work item',
    });
  }
});
