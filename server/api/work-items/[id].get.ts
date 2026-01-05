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
        message: "Invalid work item ID",
      });
    }

    const workItems = await db
      .select({
        workItem: schema.workItems,
        projectCreatedBy: schema.projects.createdBy,
      })
      .from(schema.workItems)
      .innerJoin(
        schema.projects,
        eq(schema.workItems.projectId, schema.projects.id)
      )
      .where(eq(schema.workItems.id, id))
      .limit(1);

    if (workItems.length === 0) {
      throw createError({
        statusCode: 404,
        message: "Work item not found",
      });
    }

    const { workItem, projectCreatedBy } = workItems[0];

    // Check if the work item's project belongs to the current user
    if (projectCreatedBy !== user.id) {
      throw createError({
        statusCode: 403,
        message: "Access denied",
      });
    }

    return {
      success: true,
      workItem,
    };
  } catch (error) {
    console.error("Work item fetch error:", error);
    if (error && typeof error === "object" && "statusCode" in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error ? error.message : "Failed to fetch work item",
    });
  }
});
