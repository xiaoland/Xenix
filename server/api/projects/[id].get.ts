import { db, schema } from '../../database';
import { eq } from 'drizzle-orm';
import { safeParseJsonArray } from '../../utils/datasetUtils';

export default defineEventHandler(async (event) => {
  try {
    const projectId = getRouterParam(event, 'id');

    if (!projectId) {
      throw createError({
        statusCode: 400,
        message: 'Project ID is required',
      });
    }

    const projects = await db
      .select()
      .from(schema.projects)
      .where(eq(schema.projects.projectId, projectId))
      .limit(1);

    if (projects.length === 0) {
      throw createError({
        statusCode: 404,
        message: 'Project not found',
      });
    }

    const project = projects[0];

    return {
      success: true,
      project: {
        ...project,
        datasetIds: safeParseJsonArray(project.datasetIds, []),
        workItemIds: safeParseJsonArray(project.workItemIds, []),
      },
    };
  } catch (error) {
    console.error('Project fetch error:', error);
    if (error && typeof error === 'object' && 'statusCode' in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to fetch project',
    });
  }
});
