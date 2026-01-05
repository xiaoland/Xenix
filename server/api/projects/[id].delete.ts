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

    // Check if the project exists and belongs to the current user
    const [project] = await db
      .select()
      .from(schema.projects)
      .where(eq(schema.projects.id, id))
      .limit(1);

    if (!project) {
      throw createError({
        statusCode: 404,
        message: "Project not found",
      });
    }

    if (project.createdBy !== user.id) {
      throw createError({
        statusCode: 403,
        message: "Access denied",
      });
    }

    // Delete project (cascades to work items and datasets due to FK)
    await db.delete(schema.projects).where(eq(schema.projects.id, id));

    return {
      success: true,
      message: "Project deleted successfully",
    };
  } catch (error) {
    console.error("Project deletion error:", error);
    if (error && typeof error === "object" && "statusCode" in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error ? error.message : "Failed to delete project",
    });
  }
});
