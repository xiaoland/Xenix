import { db, schema } from '../database';
import { generateTaskId, validateExcelFile, saveUploadedFile } from '../utils/taskUtils';
import { executePythonTask } from '../utils/pythonExecutor';
import { eq } from 'drizzle-orm';
import path from 'path';

export default defineEventHandler(async (event) => {
  try {
    const formData = await readFormData(event);
    const file = formData.get('file') as File;
    const model = formData.get('model') as string;
    const tuningTaskId = formData.get('tuningTaskId') as string;
    const trainingDataPath = formData.get('trainingDataPath') as string;
    const featureColumns = formData.get('featureColumns') as string; // JSON string
    const targetColumn = formData.get('targetColumn') as string;

    if (!file) {
      throw createError({
        statusCode: 400,
        message: 'No file uploaded',
      });
    }

    if (!validateExcelFile(file.name)) {
      throw createError({
        statusCode: 400,
        message: 'Invalid file type. Only Excel files (.xlsx, .xls) are allowed.',
      });
    }

    if (!model) {
      throw createError({
        statusCode: 400,
        message: 'Model name is required',
      });
    }

    if (!tuningTaskId) {
      throw createError({
        statusCode: 400,
        message: 'Tuning task ID is required (must select a trained model)',
      });
    }

    if (!trainingDataPath) {
      throw createError({
        statusCode: 400,
        message: 'Training data path is required',
      });
    }

    if (!featureColumns || !targetColumn) {
      throw createError({
        statusCode: 400,
        message: 'Feature columns and target column are required',
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
        message: 'Tuning results not found for the specified task ID',
      });
    }

    // Save uploaded prediction file
    const uploadDir = path.join(process.cwd(), 'uploads');
    const inputFile = await saveUploadedFile(file, uploadDir);
    
    // Generate output file path
    const outputFile = inputFile.replace(/\.(xlsx|xls)$/i, '_predicted.xlsx');

    // Generate task ID for prediction
    const taskId = generateTaskId();

    // Create task record
    await db.insert(schema.tasks).values({
      taskId,
      type: 'prediction',
      status: 'pending',
      model,
      inputFile,
      outputFile,
    });

    // Get Python script path for prediction
    const scriptPath = path.join(process.cwd(), 'app', 'models', 'regression', 'predict.py');
    
    // Prepare stdin data (includes params from database)
    const stdinData = {
      trainingDataPath: trainingDataPath,
      predictionDataPath: inputFile,
      outputPath: outputFile,
      model: model,
      params: modelResult.params, // Parameters from database (not from Python)
      featureColumns: parsedFeatureColumns,
      targetColumn: targetColumn
    };
    
    // Execute Python task in background
    setImmediate(() => {
      executePythonTask({
        script: scriptPath,
        stdinData: stdinData,
        taskId,
        cwd: path.join(process.cwd(), 'app', 'models', 'regression'),
      }).catch(error => {
        console.error(`Failed to execute task ${taskId}:`, error);
      });
    });

    return {
      success: true,
      taskId,
      message: 'Prediction started',
      outputFile,
    };
  } catch (error) {
    console.error('Predict error:', error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to start prediction',
    });
  }
});
