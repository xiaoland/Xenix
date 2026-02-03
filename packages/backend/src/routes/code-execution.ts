import { eq } from "drizzle-orm";
import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";

import {
  CreateCodeExecutionTaskSchema,
  TaskIdParamSchema,
} from "@xenix/shared";

import { db, schema } from "../database";
import { NotFoundError } from "../errors";
import { authMiddleware, requireAuth } from "../middleware/auth";
import logger from "../utils/logger";
import { executePythonCode } from "../utils/pythonExecutor";
import { generateTraceId } from "../utils/taskUtils";

const codeExecution = new Hono()
  .use("*", authMiddleware)

  // Execute Python code
  .post("/", zValidator("json", CreateCodeExecutionTaskSchema), async (c) => {
    const user = requireAuth(c);
    const { workItemId, code, inputs, timeout } = c.req.valid("json");

    const traceId = workItemId
      ? generateTraceId(workItemId)
      : `user.${user.id}`;

    logger.info({ traceId, workItemId }, "Starting code execution task");

    // Create task record
    const [insertedTask] = await db
      .insert(schema.tasks)
      .values({
        workItemId: workItemId || null,
        mlBackendDeploymentId: 0, // Code execution doesn't need ML backend
        type: "code-execution",
        status: "running",
        parameter: {
          code,
          inputs,
          timeout,
        },
        startedAt: new Date(),
      })
      .returning();

    try {
      // Execute Python code
      const result = await executePythonCode({
        code,
        inputs,
        timeout,
      });

      // Update task with result
      await db
        .update(schema.tasks)
        .set({
          status: "completed",
          result: {
            output: result.output,
            result: result.result,
            executionTime: result.executionTime,
          },
          endAt: new Date(),
        })
        .where(eq(schema.tasks.id, insertedTask.id));

      logger.info(
        {
          traceId,
          taskId: insertedTask.id,
          executionTime: result.executionTime,
        },
        "Code execution completed successfully",
      );

      return c.json(
        {
          taskId: insertedTask.id,
          status: "completed",
          result: {
            output: result.output,
            result: result.result,
            executionTime: result.executionTime,
          },
        },
        201,
      );
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error";

      // Update task with error
      await db
        .update(schema.tasks)
        .set({
          status: "failed",
          error: errorMessage,
          endAt: new Date(),
        })
        .where(eq(schema.tasks.id, insertedTask.id));

      logger.error(
        { traceId, taskId: insertedTask.id, error: errorMessage },
        "Code execution failed",
      );

      return c.json(
        {
          taskId: insertedTask.id,
          status: "failed",
          error: errorMessage,
        },
        500,
      );
    }
  })

  // Get code execution task result
  .get("/:id", zValidator("param", TaskIdParamSchema), async (c) => {
    const { id: idStr } = c.req.valid("param");
    const taskId = parseInt(idStr);

    const [task] = await db
      .select()
      .from(schema.tasks)
      .where(eq(schema.tasks.id, taskId))
      .limit(1);

    if (!task) {
      throw new NotFoundError("Task");
    }

    if (task.type !== "code-execution") {
      return c.json(
        {
          error: "Task is not a code execution task",
        },
        400,
      );
    }

    return c.json(task);
  });

export default codeExecution;
