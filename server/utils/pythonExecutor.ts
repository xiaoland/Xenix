import { spawn } from 'child_process';
import { db, schema } from '../database';
import { eq } from 'drizzle-orm';
import { generateTraceId } from './taskUtils';

export interface PythonTaskOptions {
  script: string;
  stdinData: any; // JSON data to pass via stdin
  taskId: number; // Changed from string to number (tasks.id)
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
  const traceId = generateTraceId(taskId);
  
  try {
    // Update task status to running and set startedAt
    await db.update(schema.tasks)
      .set({ 
        status: 'running',
        startedAt: new Date()
      })
      .where(eq(schema.tasks.id, taskId));

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
            console.log(`[${traceId}] ${line}`);
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
            console.error(`[${traceId}] ${line}`);
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
            endAt: new Date()
          })
          .where(eq(schema.tasks.id, taskId));
        
        console.log(`[${traceId}] Task completed successfully`);
      } else {
        // Task failed
        await db.update(schema.tasks)
          .set({ 
            status: 'failed',
            error: stderrBuffer || `Process exited with code ${code}`,
            endAt: new Date()
          })
          .where(eq(schema.tasks.id, taskId));
        
        console.error(`[${traceId}] Task failed with code ${code}`);
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
          endAt: new Date()
        })
        .where(eq(schema.tasks.id, taskId));
      
      console.error(`[${traceId}] Failed to start task:`, error);
    });

  } catch (error) {
    if (taskCompleted) return; // Prevent duplicate updates
    taskCompleted = true;
    
    // Update task status to failed
    await db.update(schema.tasks)
      .set({ 
        status: 'failed',
        error: error instanceof Error ? error.message : 'Unknown error',
        endAt: new Date()
      })
      .where(eq(schema.tasks.id, taskId));
    
    throw error;
  }
}

async function handleStructuredOutput(output: StructuredOutput, taskId: number) {
  const traceId = generateTraceId(taskId);
  
  try {
    switch (output.type) {
      case 'log':
        // Store log in database with task.{id} trace format
        await storeLog(output.data, taskId);
        break;
      
      case 'status':
        // Update task status
        await db.update(schema.tasks)
          .set({
            status: output.data.status,
            error: output.data.error || null
          })
          .where(eq(schema.tasks.id, taskId));
        break;
      
      case 'result':
        // Store result in tasks.result field as JSON
        await db.update(schema.tasks)
          .set({
            result: {
              model: output.data.model,
              params: output.data.params,
              metrics: output.data.metrics,
              parentTaskId: output.data.parentTaskId || null,
              trainingType: output.data.trainingType || 'auto'
            }
          })
          .where(eq(schema.tasks.id, taskId));
        break;
      
      // Note: comparison_result is deprecated (no longer used)
      // Evaluation metrics are now stored directly from tuning
        
      case 'prediction_result':
        // Store prediction result in tasks.result field
        await db.update(schema.tasks)
          .set({
            result: {
              num_predictions: output.data.num_predictions,
              outputFile: output.data.output_file
            }
          })
          .where(eq(schema.tasks.id, taskId));
        
        console.log(`[${traceId}] Prediction completed: ${output.data.num_predictions} predictions`);
        break;
    }
  } catch (error) {
    console.error(`[${traceId}] Error handling structured output:`, error);
  }
}

async function storeLog(logData: any, taskId: number) {
  const traceId = generateTraceId(taskId);
  
  try {
    await db.insert(schema.logs).values({
      timestamp: logData.timestamp,
      observedTimestamp: logData.observed_timestamp,
      traceId: traceId, // Use task.{id} format
      spanId: logData.span_id || null,
      severityText: logData.severity_text,
      severityNumber: logData.severity_number,
      body: logData.body,
      resource: logData.resource || null,
      attributes: logData.attributes || null,
      createdAt: new Date()
    });
  } catch (error) {
    console.error(`[${traceId}] Error storing log:`, error);
  }
}

/**
 * Execute a Python script synchronously and return the result
 * Used for scripts that don't need task tracking (like model scanning)
 */
export async function executePythonScript(scriptPath: string, stdinData: any): Promise<any> {
  return new Promise((resolve, reject) => {
    const pythonCmd = process.env.PYTHON_EXECUTABLE || 'python3';
    
    const pythonProcess = spawn(pythonCmd, [scriptPath], {
      cwd: process.cwd(),
      env: process.env,
    });

    // Write JSON data to stdin
    if (stdinData) {
      pythonProcess.stdin.write(JSON.stringify(stdinData));
      pythonProcess.stdin.end();
    }

    let stdoutBuffer = '';
    let stderrBuffer = '';

    pythonProcess.stdout.on('data', (data) => {
      stdoutBuffer += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
      stderrBuffer += data.toString();
    });

    pythonProcess.on('close', (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdoutBuffer);
          resolve(result);
        } catch (error) {
          reject(new Error(`Failed to parse JSON output: ${stdoutBuffer}`));
        }
      } else {
        reject(new Error(`Python script failed with code ${code}: ${stderrBuffer}`));
      }
    });

    pythonProcess.on('error', (error) => {
      reject(new Error(`Failed to execute Python script: ${error.message}`));
    });
  });
}
