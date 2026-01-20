import { eq } from "drizzle-orm";
import path from "path";

import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";

import { InlinePredictSchema, FilePredictSchema } from "@xenix/shared";

import { getMLBackendService } from "../services/MLBackendService";
import { DatasetService } from "../services";
import { db, schema } from "../database";
import { BadRequestError, NotFoundError } from "../errors";
import { authMiddleware } from "../middleware/auth";
import logger from "../utils/logger";
import { storage } from "../storage";
import { config } from "../config";

const datasetService = new DatasetService();

const predict = new Hono()
  .use("*", authMiddleware)

  // Inline prediction (JSON data)
  .post("/inline", zValidator("json", InlinePredictSchema), async (c) => {
    const { predictionData, model, tuningTaskId, workItemId } =
      c.req.valid("json");

    // Load work item to get datasetId (training), featureColumns, targetColumn
    const [workItem] = await db
      .select()
      .from(schema.workItems)
      .where(eq(schema.workItems.id, workItemId))
      .limit(1);

    if (!workItem) {
      throw new NotFoundError("Work item");
    }

    if (!workItem.datasetId) {
      throw new BadRequestError("Work item does not have a training dataset");
    }

    if (!workItem.featureColumns || !workItem.targetColumn) {
      throw new BadRequestError(
        "Work item does not have feature columns or target column configured",
      );
    }

    const featureColumns = workItem.featureColumns as string[];
    const targetColumn = workItem.targetColumn as string;

    // Validate each item in predictionData has all required feature columns
    for (let i = 0; i < predictionData.length; i++) {
      const item = predictionData[i];
      for (const col of featureColumns) {
        if (!(col in item)) {
          throw new BadRequestError(
            `Item at index ${i} is missing required feature column: ${col}`,
          );
        }
      }
    }

    // Load training dataset to get trainingDataPath
    const [trainingDataset] = await db
      .select()
      .from(schema.datasets)
      .where(eq(schema.datasets.id, workItem.datasetId))
      .limit(1);

    if (!trainingDataset) {
      throw new NotFoundError("Training dataset");
    }

    // Determine train data path based on storage type
    const trainDataPath =
      config.STORAGE_TYPE === "oss"
        ? storage.getFilesystemPath(
            `datasets/${workItem.datasetId}/${trainingDataset.fileName}`,
          ) // OSS: /mnt/oss/datasets/...
        : trainingDataset.filePath; // Local: full file path

    // Load tuning task to get params (result.params)
    const [tuningTask] = await db
      .select()
      .from(schema.tasks)
      .where(eq(schema.tasks.id, tuningTaskId))
      .limit(1);

    if (!tuningTask || !tuningTask.result) {
      throw new NotFoundError("Tuning results for the specified task ID");
    }

    const result: any = tuningTask.result;
    const params = result.bestParams || result.params || {};

    // Get deployment ID from environment variable
    const deploymentId = Number(process.env.ML_BACKEND_DEPLOYMENT_ID) || 0;
    const mlService = getMLBackendService();

    // Create task record FIRST to get actual task ID
    const [insertedTask] = await db
      .insert(schema.tasks)
      .values({
        workItemId,
        mlBackendDeploymentId: deploymentId,
        type: "predict-inline",
        status: "pending",
        parameter: {
          model,
          trainingDatasetId: workItem.datasetId,
          featureColumns,
          targetColumn,
          tuningTaskId,
          predictionDataCount: predictionData.length,
        },
      })
      .returning();

    // Execute prediction via ML backend with actual task ID
    const mlRequest = mlService.predictInline(deploymentId, insertedTask.id, {
      trainDataPath,
      toPredictData: predictionData,
      model,
      params,
      featureColumns,
      targetColumn,
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
        message: "Inline prediction started",
      },
      201,
    );
  })

  // File-based prediction (uploaded file)
  .post("/file", async (c) => {
    const formData = await c.req.formData();
    const file = formData.get("file") as File;
    const workItemIdStr = formData.get("workItemId") as string;
    const model = formData.get("model") as string;
    const tuningTaskIdStr = formData.get("tuningTaskId") as string;

    if (!file) {
      throw new BadRequestError("No file uploaded");
    }

    if (!workItemIdStr || !model || !tuningTaskIdStr) {
      throw new BadRequestError(
        "Missing required fields: workItemId, model, or tuningTaskId",
      );
    }

    const workItemId = Number(workItemIdStr);
    const tuningTaskId = Number(tuningTaskIdStr);

    // Load work item to get datasetId (training), featureColumns, targetColumn
    const [workItem] = await db
      .select()
      .from(schema.workItems)
      .where(eq(schema.workItems.id, workItemId))
      .limit(1);

    if (!workItem) {
      throw new NotFoundError("Work item");
    }

    if (!workItem.datasetId) {
      throw new BadRequestError("Work item does not have a training dataset");
    }

    if (!workItem.featureColumns || !workItem.targetColumn) {
      throw new BadRequestError(
        "Work item does not have feature columns or target column configured",
      );
    }

    const featureColumns = workItem.featureColumns as string[];
    const targetColumn = workItem.targetColumn as string;

    // Load training dataset to get trainingDataPath
    const [trainingDataset] = await db
      .select()
      .from(schema.datasets)
      .where(eq(schema.datasets.id, workItem.datasetId))
      .limit(1);

    if (!trainingDataset) {
      throw new NotFoundError("Training dataset");
    }

    // Determine train data path based on storage type
    const trainDataPath =
      config.STORAGE_TYPE === "oss"
        ? storage.getFilesystemPath(
            `datasets/${workItem.datasetId}/${trainingDataset.fileName}`,
          ) // OSS: /mnt/oss/datasets/...
        : trainingDataset.filePath; // Local: full file path

    // Load tuning task to get params (result.params)
    const [tuningTask] = await db
      .select()
      .from(schema.tasks)
      .where(eq(schema.tasks.id, tuningTaskId))
      .limit(1);

    if (!tuningTask || !tuningTask.result) {
      throw new NotFoundError("Tuning results for the specified task ID");
    }

    const result: any = tuningTask.result;
    const params = result.bestParams || result.params || {};

    // Save uploaded prediction file as a dataset using DatasetService
    const datasetsDir = path.join(process.cwd(), "datasets");
    const predictionDataset = await datasetService.createDataset(
      file,
      `Prediction Input - ${file.name}`,
      `Prediction input for work item ${workItemId}`,
      null, // No project association
      datasetsDir,
    );

    // Get the prediction data path for ML backend
    const toPredictDataPath =
      config.STORAGE_TYPE === "oss"
        ? storage.getFilesystemPath(
            `datasets/${predictionDataset.id}/${predictionDataset.fileName}`,
          ) // OSS: /mnt/oss/datasets/...
        : predictionDataset.filePath; // Local: full file path

    // Get deployment ID from environment variable
    const deploymentId = Number(process.env.ML_BACKEND_DEPLOYMENT_ID) || 0;
    const mlService = getMLBackendService();

    // Create task record FIRST to get actual task ID
    const [insertedTask] = await db
      .insert(schema.tasks)
      .values({
        workItemId,
        mlBackendDeploymentId: deploymentId,
        type: "predict-file",
        status: "pending",
        parameter: {
          model,
          trainingDatasetId: workItem.datasetId,
          predictionDatasetId: predictionDataset.id,
          featureColumns,
          targetColumn,
          tuningTaskId,
        },
      })
      .returning();

    // Fire ml-backend request with actual task ID
    const mlRequest = mlService.predictFile(deploymentId, insertedTask.id, {
      trainDataPath,
      toPredictDataPath,
      model,
      params,
      featureColumns,
      targetColumn,
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
        message: "File prediction started",
      },
      201,
    );
  });

export default predict;
