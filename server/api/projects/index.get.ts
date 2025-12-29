import { db, schema } from '../../database';
import { desc } from 'drizzle-orm';
import { safeParseJsonArray } from '../../utils/datasetUtils';

export default defineEventHandler(async (event) => {
  try {
    // Fetch all projects, ordered by most recent first
    const projects = await db
      .select()
      .from(schema.projects)
      .orderBy(desc(schema.projects.createdAt));

    // Parse JSON fields safely
    const projectsWithParsedFields = projects.map(project => ({
      ...project,
      datasetIds: safeParseJsonArray(project.datasetIds, []),
      workItemIds: safeParseJsonArray(project.workItemIds, []),
    }));

    return {
      success: true,
      projects: projectsWithParsedFields,
    };
  } catch (error) {
    console.error('Projects fetch error:', error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to fetch projects',
    });
  }
});
