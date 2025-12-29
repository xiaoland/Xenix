import { db, schema } from '../../database';
import { desc, eq } from 'drizzle-orm';

export default defineEventHandler(async (event) => {
  try {
    // Fetch all projects with their work items, ordered by most recent first
    const projects = await db
      .select()
      .from(schema.projects)
      .orderBy(desc(schema.projects.createdAt));

    // For each project, fetch its work items and datasets
    const projectsWithRelations = await Promise.all(
      projects.map(async (project) => {
        const workItems = await db
          .select()
          .from(schema.workItems)
          .where(eq(schema.workItems.projectId, project.id));
        
        const datasets = await db
          .select()
          .from(schema.datasets)
          .where(eq(schema.datasets.projectId, project.id));

        return {
          ...project,
          workItems,
          datasets,
        };
      })
    );

    return {
      success: true,
      projects: projectsWithRelations,
    };
  } catch (error) {
    console.error('Projects fetch error:', error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to fetch projects',
    });
  }
});
