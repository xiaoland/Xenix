import { db, schema } from "../../database";
import { eq, inArray } from "drizzle-orm";

export default defineEventHandler(async (event) => {
  try {
    const query = getQuery(event);
    const workItemId = Number(query.workItemId);
    const typeFilter = query.type as string | undefined;

    if (isNaN(workItemId)) {
      throw createError({
        statusCode: 400,
        message: "Invalid work item ID",
      });
    }

    let tasksQuery = db
      .select()
      .from(schema.tasks)
      .where(eq(schema.tasks.workItemId, workItemId));

    // Filter by type if specified
    if (typeFilter) {
      const types = typeFilter.split(",").map((t) => t.trim());
      tasksQuery = tasksQuery.where(inArray(schema.tasks.type, types)) as any;
    }

    const tasks = await tasksQuery;

    return {
      success: true,
      tasks,
    };
  } catch (error) {
    console.error("Tasks fetch error:", error);
    if (error && typeof error === "object" && "statusCode" in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : "Failed to fetch tasks",
    });
  }
});
