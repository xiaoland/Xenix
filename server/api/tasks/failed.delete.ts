import { db, schema } from "../../database";
import { eq, and } from "drizzle-orm";

export default defineEventHandler(async (event) => {
  try {
    const query = getQuery(event);
    const workItemId = Number(query.workItemId);

    if (!workItemId || isNaN(workItemId)) {
      throw createError({
        statusCode: 400,
        message: "workItemId is required",
      });
    }

    // Delete all failed tasks for the work item
    const result = await db
      .delete(schema.tasks)
      .where(
        and(
          eq(schema.tasks.workItemId, workItemId),
          eq(schema.tasks.status, "failed")
        )
      );

    return {
      success: true,
      message: "Failed tasks deleted successfully",
    };
  } catch (error) {
    console.error("Failed tasks deletion error:", error);
    if (error && typeof error === "object" && "statusCode" in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error ? error.message : "Failed to delete failed tasks",
    });
  }
});
