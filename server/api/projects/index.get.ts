import { db, schema } from "../../database";
import { desc, eq } from "drizzle-orm";
import { getCurrentUser, requireAuth } from "../../utils/auth";

export default defineEventHandler(async (event) => {
  try {
    const user = requireAuth(await getCurrentUser(event));

    // Fetch projects created by the current user, ordered by most recent first
    const projects = await db
      .select()
      .from(schema.projects)
      .where(eq(schema.projects.createdBy, user.id))
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
    console.error("Projects fetch error:", error);
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error ? error.message : "Failed to fetch projects",
    });
  }
});
