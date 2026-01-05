import { db, schema } from "../../database";
import { eq } from "drizzle-orm";
import { getCurrentUser, requireAuth } from "../../utils/auth";

export default defineEventHandler(async (event) => {
  try {
    const user = requireAuth(await getCurrentUser(event));
    const body = await readBody(event);
    const { name, description, projectId } = body;

    if (!name) {
      throw createError({
        statusCode: 400,
        message: "Work item name is required",
      });
    }

    if (!projectId || isNaN(Number(projectId))) {
      throw createError({
        statusCode: 400,
        message: "Valid project ID is required",
      });
    }

    // Verify project exists and belongs to the current user
    const projects = await db
      .select()
      .from(schema.projects)
      .where(eq(schema.projects.id, Number(projectId)))
      .limit(1);

    if (projects.length === 0) {
      throw createError({
        statusCode: 404,
        message: "Project not found",
      });
    }

    const project = projects[0];

    if (project.createdBy !== user.id) {
      throw createError({
        statusCode: 403,
        message: "Access denied",
      });
    }

    // Create work item record
    const result = await db
      .insert(schema.workItems)
      .values({
        projectId: Number(projectId),
        name,
        description: description || null,
        status: "active",
      })
      .returning();

    const workItem = result[0];

    return {
      success: true,
      workItem,
      message: "Work item created successfully",
    };
  } catch (error) {
    console.error("Work item creation error:", error);
    if (error && typeof error === "object" && "statusCode" in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error ? error.message : "Failed to create work item",
    });
  }
});
