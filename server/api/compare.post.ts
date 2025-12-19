import { db, schema } from '../database';
import { generateTaskId } from '../utils/taskUtils';
import { executePythonTask } from '../utils/pythonExecutor';
import path from 'path';

export default defineEventHandler(async (event) => {
  try {
    // Generate task ID
    const taskId = generateTaskId();

    // Create task record
    await db.insert(schema.tasks).values({
      taskId,
      type: 'comparison',
      status: 'pending',
    });

    // Get Python script path for model comparison
    const scriptPath = path.join(process.cwd(), 'app', 'models', 'regression', 'compare_models.py');
    
    // Execute Python task in background
    setImmediate(() => {
      executePythonTask({
        script: scriptPath,
        args: ['--output-db', taskId],
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
