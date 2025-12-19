import { spawn } from 'child_process';
import { db, schema } from '../database';
import { eq } from 'drizzle-orm';

export interface PythonTaskOptions {
  script: string;
  args: string[];
  taskId: string;
  cwd?: string;
}

export async function executePythonTask(options: PythonTaskOptions): Promise<void> {
  const { script, args, taskId, cwd } = options;
  
  try {
    // Update task status to running
    await db.update(schema.tasks)
      .set({ 
        status: 'running',
        updatedAt: new Date()
      })
      .where(eq(schema.tasks.taskId, taskId));

    // Use python3 explicitly or from environment variable
    const pythonCmd = process.env.PYTHON_EXECUTABLE || 'python3';
    
    // Execute Python script
    const pythonProcess = spawn(pythonCmd, [script, ...args], {
      cwd: cwd || process.cwd(),
      env: process.env,
    });

    let stdout = '';
    let stderr = '';

    pythonProcess.stdout.on('data', (data) => {
      stdout += data.toString();
      console.log(`[${taskId}] ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
      stderr += data.toString();
      console.error(`[${taskId}] ${data}`);
    });

    pythonProcess.on('close', async (code) => {
      if (code === 0) {
        // Task completed successfully
        await db.update(schema.tasks)
          .set({ 
            status: 'completed',
            updatedAt: new Date()
          })
          .where(eq(schema.tasks.taskId, taskId));
        
        console.log(`[${taskId}] Task completed successfully`);
      } else {
        // Task failed
        await db.update(schema.tasks)
          .set({ 
            status: 'failed',
            error: stderr || `Process exited with code ${code}`,
            updatedAt: new Date()
          })
          .where(eq(schema.tasks.taskId, taskId));
        
        console.error(`[${taskId}] Task failed with code ${code}`);
      }
    });

    pythonProcess.on('error', async (error) => {
      // Task failed to start
      await db.update(schema.tasks)
        .set({ 
          status: 'failed',
          error: error.message,
          updatedAt: new Date()
        })
        .where(eq(schema.tasks.taskId, taskId));
      
      console.error(`[${taskId}] Failed to start task:`, error);
    });

  } catch (error) {
    // Update task status to failed
    await db.update(schema.tasks)
      .set({ 
        status: 'failed',
        error: error instanceof Error ? error.message : 'Unknown error',
        updatedAt: new Date()
      })
      .where(eq(schema.tasks.taskId, taskId));
    
    throw error;
  }
}
