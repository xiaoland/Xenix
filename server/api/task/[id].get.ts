import { db, schema } from "../../database";
import { eq } from "drizzle-orm";

export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, "id");

  if (!id) {
    throw createError({
      statusCode: 400,
      message: "Task ID is required",
    });
  }

  try {
    const taskId = parseInt(id);
    
    // Get task status
    const [task] = await db
      .select()
      .from(schema.tasks)
      .where(eq(schema.tasks.id, taskId))
      .limit(1);

    if (!task) {
      throw createError({
        statusCode: 404,
        message: "Task not found",
      });
    }

    // Extract relevant info from parameter and result
    const parameter: any = task.parameter || {};
    const result: any = task.result || {};

    return {
      success: true,
      task: {
        id: task.id,
        type: task.type,
        status: task.status,
        model: parameter.model,
        error: task.error,
        parameter: task.parameter,
        result: task.result,
        createdAt: task.createdAt,
        startedAt: task.startedAt,
        endAt: task.endAt,
      },
    };
  } catch (error) {
    console.error("Status check error:", error);
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error ? error.message : "Failed to check task status",
    });
  }
});
