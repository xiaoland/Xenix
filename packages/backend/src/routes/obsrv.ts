import { Hono } from "hono";
import { db, schema } from "../database/index.js";
import { eq, desc } from "drizzle-orm";
import { authMiddleware } from "../middleware/auth.js";
import { generateTraceId } from "../utils/taskUtils.js";
import {
  BadRequestError,
} from "../errors/index.js";
import logger from "../utils/logger/index.js";

const obsrv = new Hono()
  .use("*", authMiddleware)

  // Get task observation logs
  .get("/:id", async (c) => {
    const id = c.req.param("id");

    if (!id) {
      throw new BadRequestError("Task ID is required");
    }

    const taskId = parseInt(id);
    const traceId = generateTraceId(taskId);

    // Get logs for this task (using trace_id format: task.{id})
    const logs = await db
      .select()
      .from(schema.logs)
      .where(eq(schema.logs.traceId, traceId))
      .orderBy(desc(schema.logs.timestamp))
      .limit(500); // Limit to last 500 logs

    return c.json(
      logs.map((log) => ({
        id: log.id,
        timestamp: log.timestamp,
        severity: log.severityText,
        message: log.body,
        attributes: log.attributes,
        createdAt: log.createdAt,
      }))
    );
  });

export default obsrv;
