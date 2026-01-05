import { db, schema } from "../../database";
import { eq } from "drizzle-orm";
import { getCurrentUser, requireAuth } from "../../utils/auth";

export default defineEventHandler(async (event) => {
  try {
    const user = requireAuth(await getCurrentUser(event));
    const id = Number(getRouterParam(event, "id"));
    const body = await readBody(event);

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

    const updateData: any = {
      updatedAt: new Date(),
    };

    if (body.name !== undefined) {
      updateData.name = body.name;
    }
    if (body.description !== undefined) {
      updateData.description = body.description;
    }
    if (body.status !== undefined) {
      updateData.status = body.status;
    }

    await db
      .update(schema.projects)
      .set(updateData)
      .where(eq(schema.projects.id, id));

    return {
      success: true,
      message: "Project updated successfully",
    };
  } catch (error) {
    console.error("Project update error:", error);
    if (error && typeof error === "object" && "statusCode" in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error ? error.message : "Failed to update project",
    });
  }
});
