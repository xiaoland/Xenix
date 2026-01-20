import { and, eq, inArray, sql } from "drizzle-orm";
import path from "path";

import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";

import {
  DeleteFailedTasksQuerySchema,
  DeleteTasksByModelQuerySchema,
  GetTasksQuerySchema,
  TaskIdParamSchema,
} from "@xenix/shared";

import { db, schema } from "../database";
import { BadRequestError, NotFoundError } from "../errors";
import { authMiddleware } from "../middleware/auth";
import { MLBackendDeploymentRepository } from "../repositories/MLBackendDeploymentRepository";
import { getMLBackendService } from "../services/MLBackendService";
import logger from "../utils/logger";
import type { InferSelectModel } from "drizzle-orm";
import { mlBackendDeployments } from "../database/schema";
import { storage } from "../storage";

type MLBackendDeployment = InferSelectModel<typeof mlBackendDeployments>;

/**
 * Transform file paths in result based on deployment storage type
 * - Local: Convert relative paths to absolute file paths
 * - OSS: Convert storage keys to HTTP URLs
 */
async function transformResultPaths(
  result: any,
  deployment: MLBackendDeployment,
  taskId: number
): Promise<any> {
  if (!result) return result;

  const storageType = deployment.storage || 'local';

  // For local storage, transform relative paths to absolute file paths
  if (storageType === 'local') {
    // Get ML_BASE_PATH from environment or use default
    const mlBasePath = process.env.ML_BASE_PATH || '/tmp/ml-backend';
    const taskBasePath = path.join(mlBasePath, 'tasks', String(taskId));

    const transformed = { ...result };

    // Transform predictedDataPath if exists and is relative
    if (result.predictedDataPath && !path.isAbsolute(result.predictedDataPath)) {
      transformed.predictedDataPath = path.join(taskBasePath, result.predictedDataPath);
    }

    // Transform fittedModelPath if exists and is relative
    if (result.fittedModelPath && !path.isAbsolute(result.fittedModelPath)) {
      transformed.fittedModelPath = path.join(taskBasePath, result.fittedModelPath);
    }

    return transformed;
  }

  // For OSS storage, transform storage keys to presigned HTTP URLs
  if (storageType === 'oss') {
    const transformed = { ...result };

    // Transform predictedDataPath to presigned URL (24 hour expiry)
    if (result.predictedDataPath) {
      const key = `tasks/${taskId}/${result.predictedDataPath}`;
      transformed.predictedDataPath = await storage.generatePresignedDownloadUrl(key, 86400);
    }

    // Transform fittedModelPath to presigned URL (24 hour expiry)
    if (result.fittedModelPath) {
      const key = `tasks/${taskId}/${result.fittedModelPath}`;
      transformed.fittedModelPath = await storage.generatePresignedDownloadUrl(key, 86400);
    }

    return transformed;
  }

  return result;
}

const tasks = new Hono()
  .use("*", authMiddleware)

  // Get all tasks for a work item
  .get("/", zValidator("query", GetTasksQuerySchema), async (c) => {
    const { workItemId: workItemIdStr, type: typeFilter } =
      c.req.valid("query");

    const conditions = [eq(schema.tasks.workItemId, Number(workItemIdStr))];

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

    // If task is pending or running, try to check for results (fire-and-forget)
    if (task.status === "pending" || task.status === "running") {
      // Fire-and-forget result checking
      setImmediate(async () => {
        try {
          const deploymentRepo = new MLBackendDeploymentRepository();
          const deployment = await deploymentRepo.findById(
            task.mlBackendDeploymentId,
          );

          if (!deployment) {
            throw new Error(
              `Deployment ${task.mlBackendDeploymentId} not found`,
            );
          }

          const mlService = getMLBackendService();

          // First check status to see if task is completed
          const status = await mlService.checkStatus(deployment, taskId);

          if (status === "completed") {
            // Task completed - fetch result
            const result = await mlService.checkResult(deployment, taskId);

            if (result) {
              // Transform file paths based on storage type
              const transformedResult = await transformResultPaths(result, deployment, taskId);

              await db
                .update(schema.tasks)
                .set({
                  status: "completed",
                  result: transformedResult,
                  endAt: new Date(),
                })
                .where(eq(schema.tasks.id, taskId));

              logger.info(
                { taskId },
                "Updated task with ML backend result",
              );
            }
          } else if (status === "failed") {
            // Task failed - fetch error details
            const result = await mlService.checkResult(deployment, taskId);

            await db
              .update(schema.tasks)
              .set({
                status: "failed",
                error: result?.error || "Task failed",
                endAt: new Date(),
              })
              .where(eq(schema.tasks.id, taskId));

            logger.warn(
              { taskId, error: result?.error },
              "Task failed in ML backend",
            );
          } else if (status === "running" && task.status === "pending") {
            // Update status from pending to running
            await db
              .update(schema.tasks)
              .set({
                status: "running",
                startedAt: new Date(),
              })
              .where(eq(schema.tasks.id, taskId));

            logger.info(
              { taskId },
              "Task started running in ML backend",
            );
          }
        } catch (error) {
          // Silently ignore errors in result checking
          logger.debug(
            {
              taskId,
              error: error instanceof Error ? error.message : String(error),
            },
            "Failed to check task result (non-critical)",
          );
        }
      });
    }

    return c.json(task);
  })

  // Delete all failed tasks for a work item
  .delete(
    "/failed",
    zValidator("query", DeleteFailedTasksQuerySchema),
    async (c) => {
      const { workItemId: workItemIdStr } = c.req.valid("query");

      // Delete all failed tasks for the work item
      await db
        .delete(schema.tasks)
        .where(
          and(
            eq(schema.tasks.workItemId, Number(workItemIdStr)),
            eq(schema.tasks.status, "failed"),
          ),
        );

      return c.json({
        message: "Failed tasks deleted successfully",
      });
    },
  )

  // Delete tasks by model
  .delete(
    "/model",
    zValidator("query", DeleteTasksByModelQuerySchema),
    async (c) => {
      const { workItemId: workItemIdStr, model } = c.req.valid("query");

      // Delete all tasks for the work item and model
      await db
        .delete(schema.tasks)
        .where(
          and(
            eq(schema.tasks.workItemId, Number(workItemIdStr)),
            sql`${schema.tasks.parameter} ->> 'model' = ${model}`,
          ),
        );

      return c.json({
        message: `Tasks for model ${model} deleted successfully`,
      });
    },
  );

export default tasks;
