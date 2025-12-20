import { spawn } from 'child_process';
import { db, schema } from '../database';
import { eq } from 'drizzle-orm';

export interface PythonTaskOptions {
  script: string;
  stdinData: any; // JSON data to pass via stdin
  taskId: string;
  cwd?: string;
}

// Pattern for structured output from Python scripts
interface StructuredOutput {
  type: 'log' | 'status' | 'result' | 'comparison_result' | 'prediction_result';
  data: any;
}

export async function executePythonTask(options: PythonTaskOptions): Promise<void> {
  const { script, stdinData, taskId, cwd } = options;
  
  let taskCompleted = false; // Flag to prevent race conditions
  
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
    
    // Execute Python script (no CLI args, use stdin instead)
    const pythonProcess = spawn(pythonCmd, [script], {
      cwd: cwd || process.cwd(),
      env: process.env,
    });

    // Write JSON data to stdin
    if (stdinData) {
      pythonProcess.stdin.write(JSON.stringify(stdinData));
      pythonProcess.stdin.end();
    }

    let stdoutBuffer = '';
    let stderrBuffer = '';

    pythonProcess.stdout.on('data', async (data) => {
      const output = data.toString();
      stdoutBuffer += output;
      
      // Process line by line
      const lines = stdoutBuffer.split('\n');
      stdoutBuffer = lines.pop() || ''; // Keep incomplete line in buffer
      
      for (const line of lines) {
        if (line.trim()) {
          try {
            // Try to parse as JSON structured output
            const parsed: StructuredOutput = JSON.parse(line);
            await handleStructuredOutput(parsed, taskId);
          } catch {
            // Not JSON, just log as plain text
            console.log(`[${taskId}] ${line}`);
          }
        }
      }
    });

    pythonProcess.stderr.on('data', async (data) => {
      const output = data.toString();
      stderrBuffer += output;
      
      // Process line by line
      const lines = stderrBuffer.split('\n');
      stderrBuffer = lines.pop() || ''; // Keep incomplete line in buffer
      
      for (const line of lines) {
        if (line.trim()) {
          try {
            // Try to parse as JSON structured output (logs can come from stderr)
            const parsed: StructuredOutput = JSON.parse(line);
            await handleStructuredOutput(parsed, taskId);
          } catch {
            // Not JSON, just log as error
            console.error(`[${taskId}] ${line}`);
          }
        }
      }
    });

    pythonProcess.on('close', async (code) => {
      if (taskCompleted) return; // Prevent duplicate updates
      taskCompleted = true;
      
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
            error: stderrBuffer || `Process exited with code ${code}`,
            updatedAt: new Date()
          })
          .where(eq(schema.tasks.taskId, taskId));
        
        console.error(`[${taskId}] Task failed with code ${code}`);
      }
    });

    pythonProcess.on('error', async (error) => {
      if (taskCompleted) return; // Prevent duplicate updates
      taskCompleted = true;
      
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
    if (taskCompleted) return; // Prevent duplicate updates
    taskCompleted = true;
    
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

async function handleStructuredOutput(output: StructuredOutput, taskId: string) {
  try {
    switch (output.type) {
      case 'log':
        // Store log in database
        await storeLog(output.data, taskId);
        break;
      
      case 'status':
        // Update task status
        await db.update(schema.tasks)
          .set({
            status: output.data.status,
            error: output.data.error || null,
            updatedAt: new Date()
          })
          .where(eq(schema.tasks.taskId, taskId));
        break;
      
      case 'result':
        // Store model result
        await db.insert(schema.modelResults).values({
          taskId: taskId,
          model: output.data.model,
          params: output.data.params,
          mse_train: output.data.metrics.mse_train?.toString(),
          mae_train: output.data.metrics.mae_train?.toString(),
          r2_train: output.data.metrics.r2_train?.toString(),
          mse_test: output.data.metrics.mse_test?.toString(),
          mae_test: output.data.metrics.mae_test?.toString(),
          r2_test: output.data.metrics.r2_test?.toString(),
          createdAt: new Date()
        });
        break;
      
      case 'comparison_result':
        // Store comparison result (if needed for future use)
        await db.insert(schema.comparisonResults).values({
          taskId: taskId,
          results: output.data.results,
          bestModel: output.data.best_model,
          createdAt: new Date()
        });
        break;
        
      case 'prediction_result':
        // Log prediction completion (file already saved by Python script)
        console.log(`[${taskId}] Prediction completed: ${output.data.num_predictions} predictions`);
        break;
    }
  } catch (error) {
    console.error(`[${taskId}] Error handling structured output:`, error);
  }
}

async function storeLog(logData: any, taskId: string) {
  try {
    await db.insert(schema.logs).values({
      timestamp: logData.timestamp,
      observedTimestamp: logData.observed_timestamp,
      traceId: taskId,
      spanId: logData.span_id || null,
      severityText: logData.severity_text,
      severityNumber: logData.severity_number,
      body: logData.body,
      resource: logData.resource || null,
      attributes: logData.attributes || null,
      createdAt: new Date()
    });
  } catch (error) {
    console.error(`[${taskId}] Error storing log:`, error);
  }
}
