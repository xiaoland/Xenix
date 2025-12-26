import { db, schema } from "../database";
import {
  generateTaskId,
  validateExcelFile,
  saveUploadedFile,
} from "../utils/taskUtils";
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

    let inputFile: string;
    let usedDatasetId: string | null = null;

    // Support both file upload and dataset reference
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

      inputFile = dataset.filePath;
      usedDatasetId = datasetId;
    } else if (file) {
      // Upload new file (backward compatibility)
      if (!validateExcelFile(file.name)) {
        throw createError({
          statusCode: 400,
          message:
            "Invalid file type. Only Excel files (.xlsx, .xls) are allowed.",
        });
      }

      const uploadDir = path.join(process.cwd(), "uploads");
      inputFile = await saveUploadedFile(file, uploadDir);
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

    // Generate task ID
    const taskId = generateTaskId();

    // Create task record
    await db.insert(schema.tasks).values({
      taskId,
      type: "tuning",
      status: "pending",
      model,
      datasetId: usedDatasetId,
      inputFile,
    });

    // Execute tuning task in background using high-level wrapper
    setImmediate(() => {
      tune({
        inputFile,
        model,
        featureColumns: parsedFeatureColumns,
        targetColumn,
        taskId,
        paramGrid: parsedParamGrid,
        trainingType,
        parentTaskId,
      }).catch((error) => {
        console.error(`Failed to execute task ${taskId}:`, error);
      });
    });

    return {
      success: true,
      taskId,
      inputFile, // Return the file path so UI can use it later
      featureColumns: parsedFeatureColumns,
      targetColumn: targetColumn,
      message: "Model tuning started",
    };
  } catch (error) {
    console.error("Upload error:", error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : "Failed to upload file",
    });
  }
});
