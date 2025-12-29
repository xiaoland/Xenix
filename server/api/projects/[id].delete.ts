import { db, schema } from '../../database';
import { eq } from 'drizzle-orm';

export default defineEventHandler(async (event) => {
  try {
    const id = Number(getRouterParam(event, 'id'));

    if (isNaN(id)) {
      throw createError({
        statusCode: 400,
        message: 'Invalid project ID',
      });
    }

    // Delete project (cascades to work items and datasets due to FK)
    await db
      .delete(schema.projects)
      .where(eq(schema.projects.id, id));

    return {
      success: true,
      message: 'Project deleted successfully',
    };
  } catch (error) {
    console.error('Project deletion error:', error);
    if (error && typeof error === 'object' && 'statusCode' in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to delete project',
    });
  }
});
