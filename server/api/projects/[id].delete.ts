import { db, schema } from '../../database';
import { eq } from 'drizzle-orm';

export default defineEventHandler(async (event) => {
  try {
    const projectId = getRouterParam(event, 'id');

    if (!projectId) {
      throw createError({
        statusCode: 400,
        message: 'Project ID is required',
      });
    }

    await db
      .delete(schema.projects)
      .where(eq(schema.projects.projectId, projectId));

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
