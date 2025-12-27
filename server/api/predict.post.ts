import { db, schema } from "../database";
import {
  generateTaskId,
  validateExcelFile,
  saveUploadedFile,
} from "../utils/taskUtils";
import { predict } from "../business/ml";
import { eq } from "drizzle-orm";
import path from "path";

export default defineEventHandler(async (event) => {
  try {
    const formData = await readFormData(event);
    const file = formData.get("file") as File;
    const datasetId = formData.get("datasetId") as string;
    const manualInput = formData.get("manualInput") as string;
    const model = formData.get("model") as string;
    const tuningTaskId = formData.get("tuningTaskId") as string;
    const trainingDataPath = formData.get("trainingDataPath") as string;
    const trainingDatasetId = formData.get("trainingDatasetId") as string;
    const featureColumns = formData.get("featureColumns") as string; // JSON string
    const targetColumn = formData.get("targetColumn") as string;

    let inputFile: string;
    let actualTrainingDataPath: string;
    let isManualInput = false;

    // Support manual input, file upload, or dataset reference for prediction data
    if (manualInput) {
      // Create temporary Excel file from manual input
      isManualInput = true;
      const manualValues = JSON.parse(manualInput);
      const parsedFeatureColumns = JSON.parse(featureColumns);
      
      // Import xlsx library dynamically
      const XLSX = await import('xlsx');
      
      // Create a single-row dataframe with the manual input values
      const rowData: any = {};
      parsedFeatureColumns.forEach((col: string) => {
        rowData[col] = manualValues[col];
      });
      
      // Create worksheet and workbook
      const worksheet = XLSX.utils.json_to_sheet([rowData]);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Prediction');
      
      // Save to temporary file
      const uploadDir = path.join(process.cwd(), "uploads");
      const timestamp = Date.now();
      inputFile = path.join(uploadDir, `manual_input_${timestamp}.xlsx`);
      XLSX.writeFile(workbook, inputFile);
    } else if (datasetId) {
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

      inputFile = dataset.filePath;
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
        message: "Either file, datasetId, or manualInput is required for prediction data",
      });
    }

    // Support dataset reference for training data
    if (trainingDatasetId) {
      const [dataset] = await db
        .select()
        .from(schema.datasets)
        .where(eq(schema.datasets.datasetId, trainingDatasetId))
        .limit(1);

      if (!dataset) {
        throw createError({
          statusCode: 404,
          message: "Training dataset not found",
        });
      }

      actualTrainingDataPath = dataset.filePath;
    } else if (trainingDataPath) {
      // Use provided training data path (backward compatibility)
      actualTrainingDataPath = trainingDataPath;
    } else {
      throw createError({
        statusCode: 400,
        message: "Either trainingDataPath or trainingDatasetId is required",
      });
    }

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

    // Load tuned parameters from database
    const modelResult = await db.query.modelResults.findFirst({
      where: eq(schema.modelResults.taskId, tuningTaskId),
    });

    if (!modelResult) {
      throw createError({
        statusCode: 404,
        message: "Tuning results not found for the specified task ID",
      });
    }

    // Generate output file path
    const outputFile = inputFile.replace(/\.(xlsx|xls)$/i, "_predicted.xlsx");

    // Generate task ID for prediction
    const taskId = generateTaskId();

    // Create task record
    await db.insert(schema.tasks).values({
      taskId,
      type: "prediction",
      status: "pending",
      model,
      inputFile,
      outputFile,
    });

    // Execute prediction task in background using high-level wrapper
    setImmediate(() => {
      predict({
        trainingDataPath: actualTrainingDataPath,
        predictionDataPath: inputFile,
        outputPath: outputFile,
        model,
        params: modelResult.params,
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
