import { Hono } from "hono";
import { zValidator } from "@hono/zod-validator";
import { db, schema } from "../database/index.js";
import { eq, inArray, and, sql } from "drizzle-orm";
import { authMiddleware } from "../middleware/auth.js";
import {
  NotFoundError,
  BadRequestError,
} from "../errors/index.js";
import {
  GetTasksQuerySchema,
  TaskIdParamSchema,
  DeleteFailedTasksQuerySchema,
  DeleteTasksByModelQuerySchema,
} from "@xenix/shared";
import logger from "../utils/logger/index.js";

const tasks = new Hono()
  .use("*", authMiddleware)

  // Get all tasks for a work item
  .get("/", zValidator("query", GetTasksQuerySchema), async (c) => {
    const { workItemId: workItemIdStr, type: typeFilter } = c.req.valid("query");

    let conditions = [eq(schema.tasks.workItemId, Number(workItemIdStr))];

    // Filter by type if specified
    if (typeFilter) {
      const types = typeFilter.split(",").map((t) => t.trim());
      conditions.push(inArray(schema.tasks.type, types) as any);
    }

    const tasksQuery = db
      .select()
      .from(schema.tasks)
      .where(and(...conditions));

    const tasksList = await tasksQuery;

    return c.json(tasksList);
  })

  // Get single task by ID
  .get("/:id", zValidator("param", TaskIdParamSchema), async (c) => {
    const { id: idStr } = c.req.valid("param");
    const taskId = parseInt(idStr);

    // Get task status
    const [task] = await db
      .select()
      .from(schema.tasks)
      .where(eq(schema.tasks.id, taskId))
      .limit(1);

    if (!task) {
      throw new NotFoundError("Task");
    }

    return c.json(task);
  })

  // Delete all failed tasks for a work item
  .delete("/failed", zValidator("query", DeleteFailedTasksQuerySchema), async (c) => {
    const { workItemId: workItemIdStr } = c.req.valid("query");

    // Delete all failed tasks for the work item
    await db
      .delete(schema.tasks)
      .where(
        and(
          eq(schema.tasks.workItemId, Number(workItemIdStr)),
          eq(schema.tasks.status, "failed")
        )
      );

    return c.json({
      message: "Failed tasks deleted successfully",
    });
  })

  // Delete tasks by model
  .delete("/model", zValidator("query", DeleteTasksByModelQuerySchema), async (c) => {
    const { workItemId: workItemIdStr, model } = c.req.valid("query");

    // Delete all tasks for the work item and model
    await db
      .delete(schema.tasks)
      .where(
        and(
          eq(schema.tasks.workItemId, Number(workItemIdStr)),
          sql`${schema.tasks.parameter} ->> 'model' = ${model}`
        )
      );

    return c.json({
      message: `Tasks for model ${model} deleted successfully`,
    });
  });

export default tasks;
