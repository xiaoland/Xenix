import { eq } from "drizzle-orm";

import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";

import {
  CreateBatchTrainTaskSchema,
  CreateSingleTrainTaskSchema,
} from "@xenix/shared";

import { batchTrain, singleTrain } from "../business/ml";
import { db, schema } from "../database";
import { BadRequestError, NotFoundError } from "../errors";
import { authMiddleware } from "../middleware/auth";
import logger from "../utils/logger";
import { fcInvokeService } from "../services/FCInvokeService";
import { storage } from "../storage";
import { config } from "../config";

const tune = new Hono()
  .use("*", authMiddleware)

  // Batch-train endpoint
  .post(
    "/batch-train",
    zValidator("json", CreateBatchTrainTaskSchema),
    async (c) => {
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
          "featureColumns array is required and must not be empty"
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

      // Create task record with batch-train type
      const [insertedTask] = await db
        .insert(schema.tasks)
        .values({
          workItemId: workItemId || null,
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

      const taskId = insertedTask.id;

      // Execute tuning task - use FC async invoke if available, otherwise local execution
      if (fcInvokeService.isAvailable()) {
        // FC async invoke (production)
        const storageKey = `datasets/${datasetId}/${dataset.fileName}`;
        const inputFile = storage.getFilesystemPath(storageKey);

        await fcInvokeService.invokeAsync({
          functionName: 'ml-batch-train-worker',
          payload: {
            taskId,
            inputFile, // OSS mount path: /mnt/oss/datasets/...
            model,
            featureColumns,
            targetColumn,
            paramGrid,
          },
        });
      } else {
        // Local execution (development)
        setImmediate(() => {
          batchTrain({
            inputFile: dataset.filePath,
            model,
            featureColumns,
            targetColumn,
            taskId,
            paramGrid,
          }).catch((error) => {
            logger.error({ error, taskId }, `Failed to execute tune task`);
          });
        });
      }

      return c.json(
        {
          taskId,
          message: "Batch training started",
        },
        201
      );
    }
  )

  // Single-train endpoint
  .post(
    "/single-train",
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
          "featureColumns array is required and must not be empty"
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

      // Create task record with single-train type
      const [insertedTask] = await db
        .insert(schema.tasks)
        .values({
          workItemId: workItemId || null,
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

      const taskId = insertedTask.id;

      // Determine input file path based on storage type
      const inputFile = storage.getType() === 'oss'
        ? storage.getFilesystemPath(`datasets/${datasetId}/${dataset.fileName}`) // OSS: /mnt/oss/datasets/...
        : dataset.filePath; // Local: full file path

      // Invoke ML task via adapter (automatically chooses FC or spawn)
      setImmediate(() => {
        singleTrain({
          inputFile,
          model,
          featureColumns,
          targetColumn,
          taskId,
          parameters,
        }).catch((error) => {
          logger.error({ error, taskId }, `Failed to execute manual tune task`);
        });
      });

      return c.json(
        {
          taskId,
          message: "Single training started",
        },
        201
      );
    }
  );

export default tune;
