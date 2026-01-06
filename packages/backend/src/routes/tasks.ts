import { Hono } from "hono";
import { HTTPException } from "hono/http-exception";
import { db, schema } from "../database/index.js";
import { eq, inArray, and, sql } from "drizzle-orm";
import { authMiddleware } from "../middleware/auth.js";

const tasks = new Hono()
  .use("*", authMiddleware)

  // Get all tasks for a work item
  .get("/", async (c) => {
    try {
      const workItemId = c.req.query("workItemId");
      const typeFilter = c.req.query("type");

      if (!workItemId || isNaN(Number(workItemId))) {
        throw new HTTPException(400, { message: "Invalid work item ID" });
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

      return c.json({
        success: true,
        tasks: tasksList,
      });
    } catch (error) {
      console.error("Tasks fetch error:", error);
      if (error instanceof HTTPException) {
        throw error;
      }
      throw new HTTPException(500, {
        message:
          error instanceof Error ? error.message : "Failed to fetch tasks",
      });
    }
  })

  // Get single task by ID
  .get("/:id", async (c) => {
    const id = c.req.param("id");

    if (!id) {
      throw new HTTPException(400, { message: "Task ID is required" });
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
        throw new HTTPException(404, { message: "Task not found" });
      }

      // Extract relevant info from parameter and result
      const parameter: any = task.parameter || {};
      const result: any = task.result || {};

      return c.json({
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
      });
    } catch (error) {
      console.error("Status check error:", error);
      if (error instanceof HTTPException) {
        throw error;
      }
      throw new HTTPException(500, {
        message:
          error instanceof Error
            ? error.message
            : "Failed to check task status",
      });
    }
  })

  // Delete failed tasks
  .delete("/failed", async (c) => {
    try {
      const workItemId = c.req.query("workItemId");

      if (!workItemId || isNaN(Number(workItemId))) {
        throw new HTTPException(400, { message: "workItemId is required" });
      }

      // Delete all failed tasks for the work item
      const result = await db
        .delete(schema.tasks)
        .where(
          and(
            eq(schema.tasks.workItemId, Number(workItemId)),
            eq(schema.tasks.status, "failed")
          )
        );

      return c.json({
        success: true,
        message: "Failed tasks deleted successfully",
      });
    } catch (error) {
      console.error("Failed tasks deletion error:", error);
      if (error instanceof HTTPException) {
        throw error;
      }
      throw new HTTPException(500, {
        message:
          error instanceof Error
            ? error.message
            : "Failed to delete failed tasks",
      });
    }
  })

  // Delete tasks by model
  .delete("/model", async (c) => {
    try {
      const workItemId = c.req.query("workItemId");
      const model = c.req.query("model");

      if (!workItemId || isNaN(Number(workItemId))) {
        throw new HTTPException(400, { message: "workItemId is required" });
      }

      if (!model) {
        throw new HTTPException(400, { message: "model is required" });
      }

      // Delete all tasks for the work item and model
      const result = await db
        .delete(schema.tasks)
        .where(
          and(
            eq(schema.tasks.workItemId, Number(workItemId)),
            sql`${schema.tasks.parameter} ->> 'model' = ${model}`
          )
        );

      return c.json({
        success: true,
        message: `Tasks for model ${model} deleted successfully`,
      });
    } catch (error) {
      console.error("Tasks deletion error:", error);
      if (error instanceof HTTPException) {
        throw error;
      }
      throw new HTTPException(500, {
        message:
          error instanceof Error ? error.message : "Failed to delete tasks",
      });
    }
  });

export default tasks;
