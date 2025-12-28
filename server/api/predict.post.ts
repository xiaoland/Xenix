import { db, schema } from "../database";
import { validateExcelFile, saveUploadedFile } from "../utils/taskUtils";
import { predict } from "../business/ml";
import { eq } from "drizzle-orm";
import path from "path";

export default defineEventHandler(async (event) => {
  try {
    const formData = await readFormData(event);
    const model = formData.get("model") as string;
    const parameters = formData.get("parameters") as string; // JSON string of trained params
    const trainingDatasetId = formData.get("trainingDatasetId") as string;
    const predictionDatasetId = formData.get("predictionDatasetId") as string;
    const featureColumns = formData.get("featureColumns") as string; // JSON string
    const targetColumn = formData.get("targetColumn") as string;

    // Validate required parameters
    if (!model) {
      throw createError({
        statusCode: 400,
        message: "Model name is required",
      });
    }

    if (!parameters) {
      throw createError({
        statusCode: 400,
        message: "Model parameters are required",
      });
    }

    if (!trainingDatasetId) {
      throw createError({
        statusCode: 400,
        message: "Training dataset ID is required",
      });
    }

    if (!predictionDatasetId) {
      throw createError({
        statusCode: 400,
        message: "Prediction dataset ID is required",
      });
    }

    if (!featureColumns || !targetColumn) {
      throw createError({
        statusCode: 400,
        message: "Feature columns and target column are required",
      });
    }

    // Parse parameters and features
    const parsedParameters = JSON.parse(parameters);
    const parsedFeatureColumns = JSON.parse(featureColumns);

    // Get training dataset
    const [trainingDataset] = await db
      .select()
      .from(schema.datasets)
      .where(eq(schema.datasets.datasetId, trainingDatasetId))
      .limit(1);

    if (!trainingDataset) {
      throw createError({
        statusCode: 404,
        message: "Training dataset not found",
      });
    }

    // Get prediction dataset
    const [predictionDataset] = await db
      .select()
      .from(schema.datasets)
      .where(eq(schema.datasets.datasetId, predictionDatasetId))
      .limit(1);

    if (!predictionDataset) {
      throw createError({
        statusCode: 404,
        message: "Prediction dataset not found",
      });
    }

    // Generate output file path
    const outputFile = predictionDataset.filePath.replace(/\.(xlsx|xls)$/i, "_predicted.xlsx");

    // Create task record
    const [insertedTask] = await db.insert(schema.tasks).values({
      type: "predict",
      status: "pending",
      parameter: {
        model,
        parameters: parsedParameters,
        predictionDatasetId,
        trainingDatasetId,
        featureColumns: parsedFeatureColumns,
        targetColumn,
        outputFile,
      },
    }).returning();

    const taskId = insertedTask.id;

    // Execute prediction task in background
    setImmediate(() => {
      predict({
        trainingDataPath: trainingDataset.filePath,
        predictionDataPath: predictionDataset.filePath,
        outputPath: outputFile,
        model,
        params: parsedParameters,
        featureColumns: parsedFeatureColumns,
        targetColumn,
        taskId,
      }).catch((error) => {
        console.error(`Failed to execute task ${taskId}:`, error);
      });
    });

    return {
      success: true,
      taskId,
      message: "Prediction started",
      outputFile,
    };
  } catch (error) {
    console.error("Predict error:", error);
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error ? error.message : "Failed to start prediction",
    });
  }
});
