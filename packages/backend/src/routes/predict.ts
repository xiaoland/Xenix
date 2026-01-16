import { eq } from "drizzle-orm";
import path from "path";

import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";

import { InlinePredictSchema, FilePredictSchema } from "@xenix/shared";

import { predictInline, predictFile } from "../business/ml";
import { db, schema } from "../database";
import { BadRequestError, NotFoundError } from "../errors";
import { authMiddleware } from "../middleware/auth";
import logger from "../utils/logger";

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
        "Work item does not have feature columns or target column configured"
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
            `Item at index ${i} is missing required feature column: ${col}`
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

    // Create task record first to get taskId
    const [insertedTask] = await db
      .insert(schema.tasks)
      .values({
        workItemId,
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
        },
      })
      .returning();

    const taskId = insertedTask.id;

    // Generate output file path with taskId
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const outputFile = path.join(
      process.cwd(),
      "uploads",
      `inline_prediction_${workItemId}_${taskId}_${timestamp}.xlsx`
    );

    // Update task with outputFile
    await db
      .update(schema.tasks)
      .set({
        parameter: {
          ...(insertedTask.parameter as any),
          outputFile,
        },
      })
      .where(eq(schema.tasks.id, taskId));

    // Call predictInline() in background with setImmediate
    setImmediate(() => {
      predictInline({
        trainingDataPath,
        predictionData,
        outputPath: outputFile,
        model,
        params,
        featureColumns,
        targetColumn,
        taskId,
      }).catch((error) => {
        logger.error(
          { error, taskId },
          `Failed to execute inline prediction task`
        );
      });
    });

    return c.json(
      {
        taskId,
        message: "Inline prediction started",
      },
      201
    );
  });

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
        "Missing required fields: workItemId, model, or tuningTaskId"
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
        "Work item does not have feature columns or target column configured"
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

    // Create task record first to get taskId
    const [insertedTask] = await db
      .insert(schema.tasks)
      .values({
        workItemId,
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
        },
      })
      .returning();

    const taskId = insertedTask.id;

    // Generate output file path with taskId
    const outputFile = path.join(
      uploadsDir,
      `file_prediction_${workItemId}_${taskId}_${timestamp}.xlsx`
    );

    // Update task with outputFile
    await db
      .update(schema.tasks)
      .set({
        parameter: {
          ...(insertedTask.parameter as any),
          outputFile,
        },
      })
      .where(eq(schema.tasks.id, taskId));

    // Call predictFile() in background with setImmediate
    setImmediate(() => {
      predictFile({
        trainingDataPath,
        predictionDataPath,
        outputPath: outputFile,
        model,
        params,
        featureColumns,
        targetColumn,
        taskId,
      }).catch((error) => {
        logger.error(
          { error, taskId },
          `Failed to execute file prediction task`
        );
      });
    });

    return c.json(
      {
        taskId,
        message: "File prediction started",
      },
      201
    );
  });

export default predict;
