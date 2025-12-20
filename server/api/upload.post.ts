import { db, schema } from '../database';
import { generateTaskId, validateExcelFile, saveUploadedFile } from '../utils/taskUtils';
import { executePythonTask } from '../utils/pythonExecutor';
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

    // Generate task ID
    const taskId = generateTaskId();

    // Create task record
    await db.insert(schema.tasks).values({
      taskId,
      type: 'tuning',
      status: 'pending',
      model,
      inputFile,
    });

    // Get Python script path for generic tuning script
    const scriptPath = path.join(process.cwd(), 'app', 'models', 'regression', 'tune_model.py');
    
    // Execute Python task in background
    setImmediate(() => {
      executePythonTask({
        script: scriptPath,
        args: ['--input', inputFile, '--output-db', taskId, '--model', model],
        taskId,
        cwd: path.join(process.cwd(), 'app', 'models', 'regression'),
      }).catch(error => {
        console.error(`Failed to execute task ${taskId}:`, error);
      });
    });

    return {
      success: true,
      taskId,
      inputFile, // Return the file path so UI can use it for comparison
      message: 'Model tuning started',
    };
  } catch (error) {
    console.error('Upload error:', error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to upload file',
    });
  }
});
