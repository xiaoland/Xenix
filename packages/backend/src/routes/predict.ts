import { Hono } from "hono";
import { HTTPException } from "hono/http-exception";
import { db, schema } from "../database/index.js";
import { eq } from "drizzle-orm";
import { authMiddleware } from "../middleware/auth.js";
import { predictInline } from "../business/ml/index.js";
import path from "path";

const predict = new Hono()
  .use("*", authMiddleware)

  // Inline prediction (JSON data)
  .post("/inline", async (c) => {
    try {
      const body = await c.req.json();
      const { predictionData, model, tuningTaskId, workItemId } = body;

      // Validate required fields
      if (!predictionData) {
        throw new HTTPException(400, { message: "predictionData is required" });
      }

      if (!model) {
        throw new HTTPException(400, { message: "model is required" });
      }

      if (!tuningTaskId) {
        throw new HTTPException(400, {
          message: "tuningTaskId is required (must select a trained model)",
        });
      }

      if (!workItemId) {
        throw new HTTPException(400, { message: "workItemId is required" });
      }

      // Validate predictionData is an array and has at least one item
      if (!Array.isArray(predictionData)) {
        throw new HTTPException(400, {
          message: "predictionData must be an array",
        });
      }

      if (predictionData.length === 0) {
        throw new HTTPException(400, {
          message: "predictionData must contain at least one item",
        });
      }

      // Load work item to get datasetId (training), featureColumns, targetColumn
      const [workItem] = await db
        .select()
        .from(schema.workItems)
        .where(eq(schema.workItems.id, Number(workItemId)))
        .limit(1);

      if (!workItem) {
        throw new HTTPException(404, { message: "Work item not found" });
      }

      if (!workItem.datasetId) {
        throw new HTTPException(400, {
          message: "Work item does not have a training dataset",
        });
      }

      if (!workItem.featureColumns || !workItem.targetColumn) {
        throw new HTTPException(400, {
          message:
            "Work item does not have feature columns or target column configured",
        });
      }

      const featureColumns = workItem.featureColumns as string[];
      const targetColumn = workItem.targetColumn as string;

      // Validate each item in predictionData has all required feature columns
      for (let i = 0; i < predictionData.length; i++) {
        const item = predictionData[i];
        for (const col of featureColumns) {
          if (!(col in item)) {
            throw new HTTPException(400, {
              message: `Item at index ${i} is missing required feature column: ${col}`,
            });
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
        throw new HTTPException(404, { message: "Training dataset not found" });
      }

      const trainingDataPath = trainingDataset.filePath;

      // Load tuning task to get params (result.params)
      const [tuningTask] = await db
        .select()
        .from(schema.tasks)
        .where(eq(schema.tasks.id, Number(tuningTaskId)))
        .limit(1);

      if (!tuningTask || !tuningTask.result) {
        throw new HTTPException(404, {
          message: "Tuning results not found for the specified task ID",
        });
      }

      const result: any = tuningTask.result;
      const params = result.params;

      // Create task record first to get taskId
      const [insertedTask] = await db
        .insert(schema.tasks)
        .values({
          workItemId: Number(workItemId),
          type: "predict",
          status: "pending",
          parameter: {
            model,
            trainingDatasetId: workItem.datasetId,
            featureColumns,
            targetColumn,
            tuningTaskId: Number(tuningTaskId),
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
          console.error(
            `Failed to execute inline prediction task ${taskId}:`,
            error
          );
        });
      });

      return c.json({
        success: true,
        taskId,
        message: "Inline prediction started",
      });
    } catch (error) {
      console.error("Inline predict error:", error);
      if (error instanceof HTTPException) {
        throw error;
      }
      throw new HTTPException(500, {
        message:
          error instanceof Error
            ? error.message
            : "Failed to start inline prediction",
      });
    }
  });

// TODO: by-file and generic predict endpoints
// These are complex and require file upload handling similar to datasets

export default predict;
