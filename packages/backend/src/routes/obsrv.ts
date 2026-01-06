import { Hono } from "hono";
import { HTTPException } from "hono/http-exception";
import { db, schema } from "../database/index.js";
import { eq, desc } from "drizzle-orm";
import { authMiddleware } from "../middleware/auth.js";
import { generateTraceId } from "../utils/taskUtils.js";

const obsrv = new Hono()
  .use("*", authMiddleware)

  // Get task observation logs
  .get("/:id", async (c) => {
    const id = c.req.param("id");

    if (!id) {
      throw new HTTPException(400, { message: "Task ID is required" });
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

      return c.json({
        success: true,
        logs: logs.map((log) => ({
          id: log.id,
          timestamp: log.timestamp,
          severity: log.severityText,
          message: log.body,
          attributes: log.attributes,
          createdAt: log.createdAt,
        })),
      });
    } catch (error) {
      console.error("Logs fetch error:", error);
      if (error instanceof HTTPException) {
        throw error;
      }
      throw new HTTPException(500, {
        message:
          error instanceof Error ? error.message : "Failed to fetch logs",
      });
    }
  });

export default obsrv;
