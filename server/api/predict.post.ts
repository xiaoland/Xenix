import { db, schema } from '~/server/database';
import { generateTaskId, validateExcelFile, saveUploadedFile } from '~/server/utils/taskUtils';
import { executePythonTask } from '~/server/utils/pythonExecutor';
import path from 'path';

export default defineEventHandler(async (event) => {
  try {
    const formData = await readFormData(event);
    const file = formData.get('file') as File;
    const model = formData.get('model') as string;

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

    // Save uploaded file
    const uploadDir = path.join(process.cwd(), 'uploads');
    const inputFile = await saveUploadedFile(file, uploadDir);
    
    // Generate output file path
    const outputFile = inputFile.replace(/\.(xlsx|xls)$/i, '_predicted.xlsx');

    // Generate task ID
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
    
    // Execute Python task in background
    setImmediate(() => {
      executePythonTask({
        script: scriptPath,
        args: ['--input', inputFile, '--output', outputFile, '--model', model, '--task-id', taskId],
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
    };
  } catch (error) {
    console.error('Predict error:', error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to start prediction',
    });
  }
});
