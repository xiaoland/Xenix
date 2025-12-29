import { db, schema } from '../../database';
import { desc, eq } from 'drizzle-orm';

export default defineEventHandler(async (event) => {
  try {
    const query = getQuery(event);
    const projectId = query.projectId ? Number(query.projectId) : undefined;

    let workItemsQuery = db.select().from(schema.workItems);

    // Filter by project if projectId is provided
    if (projectId && !isNaN(projectId)) {
      workItemsQuery = workItemsQuery.where(eq(schema.workItems.projectId, projectId)) as any;
    }

    const workItems = await workItemsQuery.orderBy(desc(schema.workItems.createdAt));

    return {
      success: true,
      workItems,
    };
  } catch (error) {
    console.error('Work items fetch error:', error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to fetch work items',
    });
  }
});
