import { db, schema } from "../../database";
import { predictInline } from "../../business/ml";
import { eq } from "drizzle-orm";
import path from "path";

export default defineEventHandler(async (event) => {
  try {
    const body = await readBody(event);

    const { predictionData, model, tuningTaskId, workItemId } = body;

    // Validate required fields
    if (!predictionData) {
      throw createError({
        statusCode: 400,
        message: "predictionData is required",
      });
    }

    if (!model) {
      throw createError({
        statusCode: 400,
        message: "model is required",
      });
    }

    if (!tuningTaskId) {
      throw createError({
        statusCode: 400,
        message: "tuningTaskId is required (must select a trained model)",
      });
    }

    if (!workItemId) {
      throw createError({
        statusCode: 400,
        message: "workItemId is required",
      });
    }

    // Validate predictionData is an array and has at least one item
    if (!Array.isArray(predictionData)) {
      throw createError({
        statusCode: 400,
        message: "predictionData must be an array",
      });
    }

    if (predictionData.length === 0) {
      throw createError({
        statusCode: 400,
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
      throw createError({
        statusCode: 404,
        message: "Work item not found",
      });
    }

    if (!workItem.datasetId) {
      throw createError({
        statusCode: 400,
        message: "Work item does not have a training dataset",
      });
    }

    if (!workItem.featureColumns || !workItem.targetColumn) {
      throw createError({
        statusCode: 400,
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
          throw createError({
            statusCode: 400,
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
      throw createError({
        statusCode: 404,
        message: "Training dataset not found",
      });
    }

    const trainingDataPath = trainingDataset.filePath;

    // Load tuning task to get params (result.params)
    const [tuningTask] = await db
      .select()
      .from(schema.tasks)
      .where(eq(schema.tasks.id, Number(tuningTaskId)))
      .limit(1);

    if (!tuningTask || !tuningTask.result) {
      throw createError({
        statusCode: 404,
        message: "Tuning results not found for the specified task ID",
      });
    }

    const result: any = tuningTask.result;
    const params = result.params;

    // Generate output file path for inline predictions
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const outputFile = path.join(
      process.cwd(),
      "uploads",
      `inline_prediction_${workItemId}_${taskId}_${timestamp}.xlsx`
    );

    // Create task record with type "predict" and appropriate parameters
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
          outputFile,
        },
      })
      .returning();

    const taskId = insertedTask.id;

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

    return {
      success: true,
      taskId,
      message: "Inline prediction started",
    };
  } catch (error) {
    console.error("Inline predict error:", error);
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error
          ? error.message
          : "Failed to start inline prediction",
    });
  }
});
