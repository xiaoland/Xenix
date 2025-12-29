import { db, schema } from '../../database';
import { desc } from 'drizzle-orm';

export default defineEventHandler(async (event) => {
  try {
    // Fetch all projects, ordered by most recent first
    const projects = await db
      .select()
      .from(schema.projects)
      .orderBy(desc(schema.projects.createdAt));

    // Parse JSON fields
    const projectsWithParsedFields = projects.map(project => ({
      ...project,
      datasetIds: Array.isArray(project.datasetIds) ? project.datasetIds : JSON.parse(project.datasetIds || '[]'),
      workItemIds: Array.isArray(project.workItemIds) ? project.workItemIds : JSON.parse(project.workItemIds || '[]'),
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
