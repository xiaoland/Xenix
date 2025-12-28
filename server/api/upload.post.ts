import { db, schema } from "../database";
import { validateExcelFile, saveUploadedFile } from "../utils/taskUtils";
import { tune } from "../business/ml";
import { eq } from "drizzle-orm";
import path from "path";

export default defineEventHandler(async (event) => {
  try {
    const formData = await readFormData(event);
    const file = formData.get("file") as File;
    const datasetId = formData.get("datasetId") as string;
    const model = formData.get("model") as string;
    const featureColumns = formData.get("featureColumns") as string; // JSON string
    const targetColumn = formData.get("targetColumn") as string;
    const paramGrid = formData.get("paramGrid") as string; // JSON string, optional
    const trainingType = formData.get("trainingType") as string || "auto"; // 'auto' or 'manual'
    const parentTaskId = formData.get("parentTaskId") as string; // For manual training, reference to auto-tune task

    let actualDatasetId: string;

    // Upload is for datasets - must provide either datasetId or file
    if (datasetId) {
      // Use existing dataset
      const [dataset] = await db
        .select()
        .from(schema.datasets)
        .where(eq(schema.datasets.datasetId, datasetId))
        .limit(1);

      if (!dataset) {
        throw createError({
          statusCode: 404,
          message: "Dataset not found",
        });
      }

      actualDatasetId = datasetId;
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
        description: `Uploaded for ${trainingType} training`,
        filePath: filePath,
        fileName: file.name,
        fileSize: file.size,
      });
      
      actualDatasetId = newDatasetId;
    } else {
      throw createError({
        statusCode: 400,
        message: "Either file or datasetId is required",
      });
    }

    if (!model) {
      throw createError({
        statusCode: 400,
        message: "Model name is required",
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

    // Parse param grid if provided
    const parsedParamGrid = paramGrid ? JSON.parse(paramGrid) : undefined;

    // Create task record with new schema
    const taskType = trainingType === "auto" ? "auto-tune" : "train";
    const [insertedTask] = await db.insert(schema.tasks).values({
      type: taskType,
      status: "pending",
      parameter: {
        model,
        datasetId: actualDatasetId,
        featureColumns: parsedFeatureColumns,
        targetColumn,
        paramGrid: parsedParamGrid,
        trainingType,
        parentTaskId: parentTaskId ? parseInt(parentTaskId) : undefined,
      },
    }).returning();

    const taskId = insertedTask.id;

    // Get dataset file path for execution
    const [dataset] = await db
      .select()
      .from(schema.datasets)
      .where(eq(schema.datasets.datasetId, actualDatasetId))
      .limit(1);

    // Execute tuning task in background using high-level wrapper
    setImmediate(() => {
      tune({
        inputFile: dataset!.filePath,
        model,
        featureColumns: parsedFeatureColumns,
        targetColumn,
        taskId,
        paramGrid: parsedParamGrid,
        trainingType,
        parentTaskId: parentTaskId ? parseInt(parentTaskId) : undefined,
      }).catch((error) => {
        console.error(`Failed to execute task ${taskId}:`, error);
      });
    });

    return {
      success: true,
      taskId,
      datasetId: actualDatasetId,
      featureColumns: parsedFeatureColumns,
      targetColumn: targetColumn,
      message: trainingType === "auto" ? "Auto-tune started" : "Training started",
    };
  } catch (error) {
    console.error("Upload error:", error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : "Failed to process request",
    });
  }
});
