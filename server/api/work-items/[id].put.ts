import { db, schema } from '../../database';
import { eq } from 'drizzle-orm';

export default defineEventHandler(async (event) => {
  try {
    const id = Number(getRouterParam(event, 'id'));
    const body = await readBody(event);

    if (isNaN(id)) {
      throw createError({
        statusCode: 400,
        message: 'Invalid work item ID',
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
    if (body.status !== undefined) {
      updateData.status = body.status;
    }
    // Upload step results
    if (body.datasetId !== undefined) {
      updateData.datasetId = body.datasetId ? Number(body.datasetId) : null;
    }
    if (body.featureColumns !== undefined) {
      updateData.featureColumns = body.featureColumns;
    }
    if (body.targetColumn !== undefined) {
      updateData.targetColumn = body.targetColumn;
    }

    await db
      .update(schema.workItems)
      .set(updateData)
      .where(eq(schema.workItems.id, id));

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
