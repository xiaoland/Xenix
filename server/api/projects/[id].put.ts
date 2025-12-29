import { db, schema } from '../../database';
import { eq } from 'drizzle-orm';

export default defineEventHandler(async (event) => {
  try {
    const projectId = getRouterParam(event, 'id');
    const body = await readBody(event);

    if (!projectId) {
      throw createError({
        statusCode: 400,
        message: 'Project ID is required',
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
    if (body.datasetIds !== undefined) {
      updateData.datasetIds = body.datasetIds;
    }
    if (body.workItemIds !== undefined) {
      updateData.workItemIds = body.workItemIds;
    }
    if (body.status !== undefined) {
      updateData.status = body.status;
    }

    await db
      .update(schema.projects)
      .set(updateData)
      .where(eq(schema.projects.projectId, projectId));

    return {
      success: true,
      message: 'Project updated successfully',
    };
  } catch (error) {
    console.error('Project update error:', error);
    if (error && typeof error === 'object' && 'statusCode' in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to update project',
    });
  }
});
