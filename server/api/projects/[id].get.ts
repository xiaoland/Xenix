import { db, schema } from "../../database";
import { eq } from "drizzle-orm";
import { getCurrentUser, requireAuth } from "../../utils/auth";

export default defineEventHandler(async (event) => {
  try {
    const user = requireAuth(await getCurrentUser(event));
    const id = Number(getRouterParam(event, "id"));

    if (isNaN(id)) {
      throw createError({
        statusCode: 400,
        message: "Invalid project ID",
      });
    }

    const projects = await db
      .select()
      .from(schema.projects)
      .where(eq(schema.projects.id, id))
      .limit(1);

    if (projects.length === 0) {
      throw createError({
        statusCode: 404,
        message: "Project not found",
      });
    }

    const project = projects[0];

    // Check if the project belongs to the current user
    if (project.createdBy !== user.id) {
      throw createError({
        statusCode: 403,
        message: "Access denied",
      });
    }

    // Fetch related work items and datasets
    const workItems = await db
      .select()
      .from(schema.workItems)
      .where(eq(schema.workItems.projectId, id));

    const datasets = await db
      .select()
      .from(schema.datasets)
      .where(eq(schema.datasets.projectId, id));

    return {
      success: true,
      project: {
        ...project,
        workItems,
        datasets,
      },
    };
  } catch (error) {
    console.error("Project fetch error:", error);
    if (error && typeof error === "object" && "statusCode" in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error ? error.message : "Failed to fetch project",
    });
  }
});
