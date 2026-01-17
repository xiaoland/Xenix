import { eq } from "drizzle-orm";
import path from "path";

import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";

import { InlinePredictSchema, FilePredictSchema } from "@xenix/shared";

import { getMLBackendService } from "../services/MLBackendService";
import { db, schema } from "../database";
import { BadRequestError, NotFoundError } from "../errors";
import { authMiddleware } from "../middleware/auth";
import logger from "../utils/logger";
import { fcInvokeService } from "../services/FCInvokeService";
import { storage } from "../storage";
import { config } from "../config";

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

    const trainingDataPath = trainingDataset.filePath;

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
    const params = result.params;

    // Get deployment ID from environment variable
    const deploymentId = Number(process.env.ML_BACKEND_DEPLOYMENT_ID) || 1;
    const mlService = getMLBackendService();

    // Generate temporary task ID and output file path
    const tempTaskId = Date.now();
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    let outputFile: string;

    if (fcInvokeService.isAvailable()) {
      // OSS storage key for production
      outputFile = `predictions/${tempTaskId}/inline_prediction_${workItemId}_${tempTaskId}_${timestamp}.xlsx`;
    } else {
      // Local file path for development
      outputFile = path.join(
        process.cwd(),
        "uploads",
        `inline_prediction_${workItemId}_${tempTaskId}_${timestamp}.xlsx`,
      );
    }

    // Execute prediction - use FC async invoke if available, otherwise ml-backend
    if (fcInvokeService.isAvailable()) {
      // FC async invoke (production)
      const trainingStorageKey = `datasets/${workItem.datasetId}/${trainingDataset.fileName}`;
      const trainingDataFile = storage.getFilesystemPath(trainingStorageKey);
      const outputFilePath = storage.getFilesystemPath(outputFile);

      await fcInvokeService.invokeAsync({
        functionName: "ml-predict-worker",
        payload: {
          taskId: tempTaskId,
          trainingDataFile, // OSS mount path: /mnt/oss/datasets/...
          predictionData,
          outputFile: outputFilePath, // OSS mount path: /mnt/oss/predictions/...
          model,
          params,
          featureColumns,
          targetColumn,
        },
      });
    } else {
      // Local execution via ml-backend
      const mlRequest = mlService.predictInline(deploymentId, tempTaskId, {
        trainingDataPath,
        predictionData,
        outputPath: outputFile,
        model,
        params,
        featureColumns,
        targetColumn,
      });

      // Wait 5s to check for errors (fire-and-forget pattern)
      let hasError = false;
      await Promise.race([
        mlRequest.catch((error) => {
          hasError = true;
          logger.error(
            { error: error.message, tempTaskId },
            "ML backend request failed",
          );
          throw error;
        }),
        new Promise((resolve) => setTimeout(resolve, 5000)),
      ]);

      if (hasError) {
        throw new Error("ML backend request failed");
      }
    }

    // Create task record only after successful ML backend request
    const [insertedTask] = await db
      .insert(schema.tasks)
      .values({
        workItemId,
        mlBackendDeploymentId: fcInvokeService.isAvailable() ? null : deploymentId,
        type: "predict",
        status: "pending",
        parameter: {
          model,
          trainingDatasetId: workItem.datasetId,
          featureColumns,
          targetColumn,
          tuningTaskId,
          predictionType: "inline",
          predictionDataCount: predictionData.length,
          outputFile,
        },
      })
      .returning();

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

    const trainingDataPath = trainingDataset.filePath;

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
    const params = result.params;

    // Save uploaded prediction file
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const uploadsDir = path.join(process.cwd(), "uploads");
    const predictionFileName = `prediction_input_${workItemId}_${timestamp}_${file.name}`;
    const predictionDataPath = path.join(uploadsDir, predictionFileName);

    // Save file to disk
    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    const fs = await import("fs/promises");
    await fs.mkdir(uploadsDir, { recursive: true });
    await fs.writeFile(predictionDataPath, buffer);

    // Get deployment ID from environment variable
    const deploymentId = Number(process.env.ML_BACKEND_DEPLOYMENT_ID) || 1;
    const mlService = getMLBackendService();

    // Generate temporary task ID and output file path
    const tempTaskId = Date.now();
    const outputFile = path.join(
      uploadsDir,
      `file_prediction_${workItemId}_${tempTaskId}_${timestamp}.xlsx`,
    );

    // Fire ml-backend request
    const mlRequest = mlService.predictFile(deploymentId, tempTaskId, {
      trainingDataPath,
      predictionDataPath,
      outputPath: outputFile,
      model,
      params,
      featureColumns,
      targetColumn,
    });

    // Wait 5s to check for errors (fire-and-forget pattern)
    let hasError = false;
    await Promise.race([
      mlRequest.catch((error) => {
        hasError = true;
        logger.error(
          { error: error.message, tempTaskId },
          "ML backend request failed",
        );
        throw error;
      }),
      new Promise((resolve) => setTimeout(resolve, 5000)),
    ]);

    if (hasError) {
      throw new Error("ML backend request failed");
    }

    // Create task record only after successful ML backend request
    const [insertedTask] = await db
      .insert(schema.tasks)
      .values({
        workItemId,
        mlBackendDeploymentId: deploymentId,
        type: "predict",
        status: "pending",
        parameter: {
          model,
          trainingDatasetId: workItem.datasetId,
          featureColumns,
          targetColumn,
          tuningTaskId,
          predictionType: "file",
          predictionDataPath,
          outputFile,
        },
      })
      .returning();

    return c.json(
      {
        taskId: insertedTask.id,
        message: "File prediction started",
      },
      201,
    );
  });

export default predict;
