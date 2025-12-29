import { db, schema } from '../../database';
import { eq } from 'drizzle-orm';
import { safeParseJsonArray } from '../../utils/datasetUtils';

export default defineEventHandler(async (event) => {
  try {
    const workItemId = getRouterParam(event, 'id');

    if (!workItemId) {
      throw createError({
        statusCode: 400,
        message: 'Work item ID is required',
      });
    }

    // Get work item to find its project
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

    // Remove work item from project's workItemIds
    if (workItem.projectId) {
      const projects = await db
        .select()
        .from(schema.projects)
        .where(eq(schema.projects.projectId, workItem.projectId))
        .limit(1);

      if (projects.length > 0) {
        const project = projects[0];
        const currentWorkItemIds = safeParseJsonArray(project.workItemIds, []);
        
        await db
          .update(schema.projects)
          .set({
            workItemIds: currentWorkItemIds.filter((id: string) => id !== workItemId),
            updatedAt: new Date(),
          })
          .where(eq(schema.projects.projectId, workItem.projectId));
      }
    }

    // Delete work item
    await db
      .delete(schema.workItems)
      .where(eq(schema.workItems.workItemId, workItemId));

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
