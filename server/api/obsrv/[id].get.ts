import { db, schema } from "../../database";
import { eq, desc } from "drizzle-orm";
import { generateTraceId } from "../../utils/taskUtils";

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
    const traceId = generateTraceId(taskId);
    
    // Get logs for this task (using trace_id format: task.{id})
    const logs = await db
      .select()
      .from(schema.logs)
      .where(eq(schema.logs.traceId, traceId))
      .orderBy(desc(schema.logs.timestamp))
      .limit(500); // Limit to last 500 logs

    return {
      success: true,
      logs: logs.map((log) => ({
        id: log.id,
        timestamp: log.timestamp,
        severity: log.severityText,
        message: log.body,
        attributes: log.attributes,
        createdAt: log.createdAt,
      })),
    };
  } catch (error) {
    console.error("Logs fetch error:", error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : "Failed to fetch logs",
    });
  }
});
