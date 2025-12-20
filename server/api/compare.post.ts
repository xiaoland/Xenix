import { db, schema } from '../database';
import { generateTaskId } from '../utils/taskUtils';
import { executePythonTask } from '../utils/pythonExecutor';
import path from 'path';

export default defineEventHandler(async (event) => {
  try {
    // Read request body
    const body = await readBody(event);
    const { inputFile, models, taskIds } = body;

    if (!inputFile) {
      throw createError({
        statusCode: 400,
        message: 'Input file path is required',
      });
    }

    if (!models || !Array.isArray(models) || models.length === 0) {
      throw createError({
        statusCode: 400,
        message: 'Models array is required',
      });
    }

    // Generate task ID
    const taskId = generateTaskId();

    // Create task record
    await db.insert(schema.tasks).values({
      taskId,
      type: 'comparison',
      status: 'pending',
      inputFile,
    });

    // Get Python script path for model comparison
    const scriptPath = path.join(process.cwd(), 'app', 'models', 'regression', 'compare_models.py');
    
    // Build arguments
    const args = [
      '--input', inputFile,
      '--models', models.join(',')
    ];
    
    // Add task IDs mapping if provided
    if (taskIds && Object.keys(taskIds).length > 0) {
      const taskIdMappings = Object.entries(taskIds)
        .map(([model, tid]) => `${model}=${tid}`)
        .join(',');
      args.push('--task-ids', taskIdMappings);
    }
    
    // Execute Python task in background
    setImmediate(() => {
      executePythonTask({
        script: scriptPath,
        args,
        taskId,
        cwd: path.join(process.cwd(), 'app', 'models', 'regression'),
      }).catch(error => {
        console.error(`Failed to execute task ${taskId}:`, error);
      });
    });

    return {
      success: true,
      taskId,
      message: 'Model comparison started',
    };
  } catch (error) {
    console.error('Compare error:', error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to start comparison',
    });
  }
});
