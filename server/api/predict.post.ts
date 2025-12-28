import { db, schema } from "../database";
import { validateExcelFile, saveUploadedFile } from "../utils/taskUtils";
import { predict } from "../business/ml";
import { eq } from "drizzle-orm";
import path from "path";

export default defineEventHandler(async (event) => {
  try {
    const formData = await readFormData(event);
    const file = formData.get("file") as File;
    const datasetId = formData.get("datasetId") as string;
    const model = formData.get("model") as string;
    const tuningTaskId = formData.get("tuningTaskId") as string;
    const trainingDatasetId = formData.get("trainingDatasetId") as string;
    const featureColumns = formData.get("featureColumns") as string; // JSON string
    const targetColumn = formData.get("targetColumn") as string;

    let predictionDatasetId: string;
    let trainingDataPath: string;

    // Support both file upload and dataset reference for prediction data
    if (datasetId) {
      // Use existing dataset for prediction
      const [dataset] = await db
        .select()
        .from(schema.datasets)
        .where(eq(schema.datasets.datasetId, datasetId))
        .limit(1);

      if (!dataset) {
        throw createError({
          statusCode: 404,
          message: "Prediction dataset not found",
        });
      }

      predictionDatasetId = datasetId;
    } else if (file) {
      // Upload new file and create dataset
      if (!validateExcelFile(file.name)) {
        throw createError({
          statusCode: 400,
          message:
            "Invalid file type. Only Excel files (.xlsx, .xls) are allowed.",
        });
      }

      const uploadDir = path.join(process.cwd(), "uploads");
      const filePath = await saveUploadedFile(file, uploadDir);
      
      // Create dataset record
      const newDatasetId = `ds_${Date.now()}`;
      await db.insert(schema.datasets).values({
        datasetId: newDatasetId,
        name: file.name,
        description: "Uploaded for prediction",
        filePath: filePath,
        fileName: file.name,
        fileSize: file.size,
      });
      
      predictionDatasetId = newDatasetId;
    } else {
      throw createError({
        statusCode: 400,
        message: "Either file or datasetId is required for prediction data",
      });
    }

    // Get training dataset
    if (!trainingDatasetId) {
      throw createError({
        statusCode: 400,
        message: "trainingDatasetId is required",
      });
    }

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

    trainingDataPath = trainingDataset.filePath;

    if (!model) {
      throw createError({
        statusCode: 400,
        message: "Model name is required",
      });
    }

    if (!tuningTaskId) {
      throw createError({
        statusCode: 400,
        message: "Tuning task ID is required (must select a trained model)",
      });
    }

    if (!featureColumns || !targetColumn) {
      throw createError({
        statusCode: 400,
        message: "Feature columns and target column are required",
      });
    }

    // Parse feature columns
    const parsedFeatureColumns = JSON.parse(featureColumns);

    // Load tuned parameters from database (task.result field)
    const [tuningTask] = await db
      .select()
      .from(schema.tasks)
      .where(eq(schema.tasks.id, parseInt(tuningTaskId)))
      .limit(1);

    if (!tuningTask || !tuningTask.result) {
      throw createError({
        statusCode: 404,
        message: "Tuning results not found for the specified task ID",
      });
    }

    const result: any = tuningTask.result;

    // Get prediction dataset file path
    const [predictionDataset] = await db
      .select()
      .from(schema.datasets)
      .where(eq(schema.datasets.datasetId, predictionDatasetId))
      .limit(1);

    // Generate output file path
    const outputFile = predictionDataset!.filePath.replace(/\.(xlsx|xls)$/i, "_predicted.xlsx");

    // Create task record with new schema
    const [insertedTask] = await db.insert(schema.tasks).values({
      type: "predict",
      status: "pending",
      parameter: {
        model,
        predictionDatasetId,
        trainingDatasetId,
        featureColumns: parsedFeatureColumns,
        targetColumn,
        tuningTaskId: parseInt(tuningTaskId),
        outputFile,
      },
    }).returning();

    const taskId = insertedTask.id;

    // Execute prediction task in background using high-level wrapper
    setImmediate(() => {
      predict({
        trainingDataPath,
        predictionDataPath: predictionDataset!.filePath,
        outputPath: outputFile,
        model,
        params: result.params,
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
