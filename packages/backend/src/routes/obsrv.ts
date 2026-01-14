import { desc, eq } from "drizzle-orm";

import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";

import { TaskIdParamSchema } from "@xenix/shared";

import { db, schema } from "../database";
import { BadRequestError } from "../errors";
import { authMiddleware } from "../middleware/auth";
import logger from "../utils/logger";
import { generateTraceId } from "../utils/taskUtils";

const obsrv = new Hono()
  .use("*", authMiddleware)

  // Get task observation logs
  .get("/:id", zValidator("param", TaskIdParamSchema), async (c) => {
    const { id: idStr } = c.req.valid("param");
    const taskId = parseInt(idStr);
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
