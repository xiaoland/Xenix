import { eq } from "drizzle-orm";

import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";

import {
  CreateBatchTrainTaskSchema,
  CreateSingleTrainTaskSchema,
} from "@xenix/shared";

import { getMLBackendService } from "../services/MLBackendService";
import { db, schema } from "../database";
import { BadRequestError, NotFoundError } from "../errors";
import { authMiddleware } from "../middleware/auth";
import logger from "../utils/logger";
import { storage } from "../storage";

const train = new Hono()
  .use("*", authMiddleware)

  // Batch-train endpoint
  .post("/batch", zValidator("json", CreateBatchTrainTaskSchema), async (c) => {
    let {
      datasetId,
      featureColumns,
      targetColumn,
      model,
      paramGrid,
      workItemId,
    } = c.req.valid("json");

    // If workItemId provided, try to fill missing values from the work item
    if (workItemId) {
      const [workItem] = await db
        .select()
        .from(schema.workItems)
        .where(eq(schema.workItems.id, workItemId))
        .limit(1);

      if (workItem) {
        if (!datasetId && workItem.datasetId) datasetId = workItem.datasetId;
        if (
          (!featureColumns || featureColumns.length === 0) &&
          workItem.featureColumns
        ) {
          featureColumns = workItem.featureColumns as string[];
        }
        if (!targetColumn && workItem.targetColumn)
          targetColumn = workItem.targetColumn as string;
      }
    }

    // Validate required parameters (after trying to fill from work item)
    if (!datasetId) {
      throw new BadRequestError("datasetId is required");
    }

    if (!featureColumns || featureColumns.length === 0) {
      throw new BadRequestError(
        "featureColumns array is required and must not be empty",
      );
    }

    if (!targetColumn) {
      throw new BadRequestError("targetColumn is required");
    }

    // Verify dataset exists
    const [dataset] = await db
      .select()
      .from(schema.datasets)
      .where(eq(schema.datasets.id, datasetId))
      .limit(1);

    if (!dataset) {
      throw new NotFoundError("Dataset");
    }

    // Get deployment ID from environment variable
    const deploymentId = Number(process.env.ML_BACKEND_DEPLOYMENT_ID) || 0;
    const mlService = getMLBackendService();

    // Create task record FIRST to get actual task ID
    const [insertedTask] = await db
      .insert(schema.tasks)
      .values({
        workItemId: workItemId,
        mlBackendDeploymentId: deploymentId,
        type: "batch-train",
        status: "pending",
        parameter: {
          model,
          datasetId,
          featureColumns,
          targetColumn,
          paramGrid,
        },
      })
      .returning();

    // Fire ml-backend request with actual task ID
    const mlRequest = mlService.batchTrain(deploymentId, insertedTask.id, {
      inputFile: dataset.filePath,
      model,
      featureColumns,
      targetColumn,
      paramGrid,
    });

    // Wait 5s to check for errors (fire-and-forget pattern)
    let hasError = false;
    let errorMessage = "";
    await Promise.race([
      mlRequest.catch((error) => {
        hasError = true;
        errorMessage = error.message;
        logger.error(
          { error: error.message, taskId: insertedTask.id },
          "ML backend request failed",
        );
        throw error;
      }),
      new Promise((resolve) => setTimeout(resolve, 5000)),
    ]);

    // Update task status based on error outcome
    if (hasError) {
      await db
        .update(schema.tasks)
        .set({
          status: "failed",
          error: errorMessage,
          endAt: new Date(),
        })
        .where(eq(schema.tasks.id, insertedTask.id));
    } else {
      await db
        .update(schema.tasks)
        .set({ status: "running" })
        .where(eq(schema.tasks.id, insertedTask.id));
    }

    return c.json(
      {
        taskId: insertedTask.id,
        message: "Batch training started",
      },
      201,
    );
  })

  // Single-train endpoint
  .post(
    "/single",
    zValidator("json", CreateSingleTrainTaskSchema),
    async (c) => {
      let {
        datasetId,
        featureColumns,
        targetColumn,
        model,
        parameters,
        workItemId,
      } = c.req.valid("json");

      // If workItemId provided, try to fill missing values from the work item
      if (workItemId) {
        const [workItem] = await db
          .select()
          .from(schema.workItems)
          .where(eq(schema.workItems.id, workItemId))
          .limit(1);

        if (workItem) {
          if (!datasetId && workItem.datasetId) datasetId = workItem.datasetId;
          if (
            (!featureColumns || featureColumns.length === 0) &&
            workItem.featureColumns
          ) {
            featureColumns = workItem.featureColumns as string[];
          }
          if (!targetColumn && workItem.targetColumn)
            targetColumn = workItem.targetColumn as string;
        }
      }

      // Validate required parameters (after trying to fill from work item)
      if (!datasetId) {
        throw new BadRequestError("datasetId is required");
      }

      if (!featureColumns || featureColumns.length === 0) {
        throw new BadRequestError(
          "featureColumns array is required and must not be empty",
        );
      }

      if (!targetColumn) {
        throw new BadRequestError("targetColumn is required");
      }

      // Verify dataset exists
      const [dataset] = await db
        .select()
        .from(schema.datasets)
        .where(eq(schema.datasets.id, datasetId))
        .limit(1);

      if (!dataset) {
        throw new NotFoundError("Dataset");
      }

      // Get deployment ID from environment variable
      const deploymentId = Number(process.env.ML_BACKEND_DEPLOYMENT_ID) || 1;
      const mlService = getMLBackendService();

      // Determine input file path based on storage type
      const inputFile =
        storage.getType() === "oss"
          ? storage.getFilesystemPath(
              `datasets/${datasetId}/${dataset.fileName}`,
            ) // OSS: /mnt/oss/datasets/...
          : dataset.filePath; // Local: full file path

      // Create task record FIRST to get actual task ID
      const [insertedTask] = await db
        .insert(schema.tasks)
        .values({
          workItemId: workItemId || null,
          mlBackendDeploymentId: deploymentId,
          type: "single-train",
          status: "pending",
          parameter: {
            model,
            datasetId,
            featureColumns,
            targetColumn,
            parameters,
          },
        })
        .returning();

      // Fire ml-backend request with actual task ID
      const mlRequest = mlService.singleTrain(deploymentId, insertedTask.id, {
        inputFile,
        model,
        featureColumns,
        targetColumn,
        parameters,
      });

      // Wait 5s to check for errors (fire-and-forget pattern)
      let hasError = false;
      let errorMessage = "";
      await Promise.race([
        mlRequest.catch((error) => {
          hasError = true;
          errorMessage = error.message;
          logger.error(
            { error: error.message, taskId: insertedTask.id },
            "ML backend request failed",
          );
          throw error;
        }),
        new Promise((resolve) => setTimeout(resolve, 5000)),
      ]);

      // Update task status based on error outcome
      if (hasError) {
        await db
          .update(schema.tasks)
          .set({
            status: "failed",
            error: errorMessage,
            endAt: new Date(),
          })
          .where(eq(schema.tasks.id, insertedTask.id));
      } else {
        await db
          .update(schema.tasks)
          .set({ status: "running" })
          .where(eq(schema.tasks.id, insertedTask.id));
      }

      return c.json(
        {
          taskId: insertedTask.id,
          message: "Single training started",
        },
        201,
      );
    },
  );

export default train;
