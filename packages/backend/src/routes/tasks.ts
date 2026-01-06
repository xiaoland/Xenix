import { Hono } from "hono";
import { db, schema } from "../database/index.js";
import { eq, inArray, and, sql } from "drizzle-orm";
import { authMiddleware } from "../middleware/auth.js";
import {
  NotFoundError,
  BadRequestError,
} from "../errors/index.js";
import logger from "../utils/logger/index.js";

const tasks = new Hono()
  .use("*", authMiddleware)

  // Get all tasks for a work item
  .get("/", async (c) => {
    const workItemId = c.req.query("workItemId");
    const typeFilter = c.req.query("type");

    if (!workItemId || isNaN(Number(workItemId))) {
      throw new BadRequestError("Invalid work item ID");
    }

    let conditions = [eq(schema.tasks.workItemId, Number(workItemId))];

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
  .get("/:id", async (c) => {
    const id = c.req.param("id");

    if (!id) {
      throw new BadRequestError("Task ID is required");
    }

    const taskId = parseInt(id);

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
  .delete("/failed", async (c) => {
    const workItemId = c.req.query("workItemId");

    if (!workItemId || isNaN(Number(workItemId))) {
      throw new BadRequestError("workItemId is required");
    }

    // Delete all failed tasks for the work item
    await db
      .delete(schema.tasks)
      .where(
        and(
          eq(schema.tasks.workItemId, Number(workItemId)),
          eq(schema.tasks.status, "failed")
        )
      );

    return c.json({
      message: "Failed tasks deleted successfully",
    });
  })

  // Delete tasks by model
  .delete("/model", async (c) => {
    const workItemId = c.req.query("workItemId");
    const model = c.req.query("model");

    if (!workItemId || isNaN(Number(workItemId))) {
      throw new BadRequestError("workItemId is required");
    }

    if (!model) {
      throw new BadRequestError("model is required");
    }

    // Delete all tasks for the work item and model
    await db
      .delete(schema.tasks)
      .where(
        and(
          eq(schema.tasks.workItemId, Number(workItemId)),
          sql`${schema.tasks.parameter} ->> 'model' = ${model}`
        )
      );

    return c.json({
      message: `Tasks for model ${model} deleted successfully`,
    });
  });

export default tasks;
