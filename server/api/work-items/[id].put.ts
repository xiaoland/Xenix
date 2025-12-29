import { db, schema } from '../../database';
import { eq } from 'drizzle-orm';

export default defineEventHandler(async (event) => {
  try {
    const workItemId = getRouterParam(event, 'id');
    const body = await readBody(event);

    if (!workItemId) {
      throw createError({
        statusCode: 400,
        message: 'Work item ID is required',
      });
    }

    const updateData: any = {
      updatedAt: new Date(),
    };

    if (body.name !== undefined) {
      updateData.name = body.name;
    }
    if (body.description !== undefined) {
      updateData.description = body.description;
    }
    if (body.taskIds !== undefined) {
      updateData.taskIds = body.taskIds;
    }
    if (body.status !== undefined) {
      updateData.status = body.status;
    }

    await db
      .update(schema.workItems)
      .set(updateData)
      .where(eq(schema.workItems.workItemId, workItemId));

    return {
      success: true,
      message: 'Work item updated successfully',
    };
  } catch (error) {
    console.error('Work item update error:', error);
    if (error && typeof error === 'object' && 'statusCode' in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to update work item',
    });
  }
});
