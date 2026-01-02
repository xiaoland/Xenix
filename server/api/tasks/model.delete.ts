import { db, schema } from "../../database";
import { eq, and } from "drizzle-orm";
import { sql } from "drizzle-orm";

export default defineEventHandler(async (event) => {
  try {
    const query = getQuery(event);
    const workItemId = Number(query.workItemId);
    const model = query.model as string;

    if (!workItemId || isNaN(workItemId)) {
      throw createError({
        statusCode: 400,
        message: "workItemId is required",
      });
    }

    if (!model) {
      throw createError({
        statusCode: 400,
        message: "model is required",
      });
    }

    // Delete all tasks for the work item and model
    const result = await db
      .delete(schema.tasks)
      .where(
        and(
          eq(schema.tasks.workItemId, workItemId),
          sql`${schema.tasks.parameter} ->> 'model' = ${model}`
        )
      );

    return {
      success: true,
      message: `Tasks for model ${model} deleted successfully`,
    };
  } catch (error) {
    console.error("Tasks deletion error:", error);
    if (error && typeof error === "object" && "statusCode" in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error ? error.message : "Failed to delete tasks",
    });
  }
});
