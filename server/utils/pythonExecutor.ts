import { spawn } from 'child_process';
import path from 'path';
import { db, schema } from '../database';
import { eq } from 'drizzle-orm';

// Constants for Docker configuration
const CONTAINER_ROOT_PATH = '/app';

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

/**
 * Get the execution mode from environment variable
 */
export function getExecutionMode(): 'local' | 'docker' {
  const mode = process.env.PYTHON_EXECUTION_MODE?.toLowerCase();
  return mode === 'docker' ? 'docker' : 'local';
}

/**
 * Execute Python task in local mode (direct Python execution)
 */
function executeLocalPython(options: PythonTaskOptions) {
  const { script, stdinData, cwd } = options;
  const pythonCmd = process.env.PYTHON_EXECUTABLE || 'python3';
  
  const pythonProcess = spawn(pythonCmd, [script], {
    cwd: cwd || process.cwd(),
    env: process.env,
  });

  // Write JSON data to stdin
  if (stdinData) {
    pythonProcess.stdin.write(JSON.stringify(stdinData));
    pythonProcess.stdin.end();
  }

  return pythonProcess;
}

/**
 * Execute Python task in Docker mode (run Python in Docker container)
 */
function executeDockerPython(options: PythonTaskOptions) {
  const { script, stdinData, cwd } = options;
  
  // Get container name from environment or use default
  const containerName = process.env.PYTHON_CONTAINER_NAME || 'xenix-python-ml';
  
  // Convert absolute path to container path
  const scriptPath = path.resolve(script);
  const hostRoot = process.cwd();
  
  if (!scriptPath.startsWith(hostRoot)) {
    throw new Error(`Script path ${scriptPath} is not within project directory ${hostRoot}`);
  }
  
  // Convert to container path using proper path operations
  const relativePath = path.relative(hostRoot, scriptPath);
  const scriptInContainer = path.join(CONTAINER_ROOT_PATH, relativePath).replace(/\\/g, '/'); // Normalize for Unix
  
  // Use docker exec to run Python script in the running container
  const dockerProcess = spawn('docker', [
    'exec',
    '-i', // Keep stdin open
    containerName,
    'pdm', 'run', 'python3',
    scriptInContainer
  ], {
    cwd: cwd || process.cwd(),
    env: process.env,
  });

  // Write JSON data to stdin
  if (stdinData) {
    // Need to adjust file paths in stdinData to container paths
    const adjustedData = adjustPathsForDocker(stdinData);
    dockerProcess.stdin.write(JSON.stringify(adjustedData));
    dockerProcess.stdin.end();
  }

  return dockerProcess;
}

/**
 * Adjust file paths in data object for Docker container
 */
function adjustPathsForDocker(data: any): any {
  if (!data || typeof data !== 'object') {
    return data;
  }

  const adjusted = { ...data };
  const pathKeys = ['inputFile', 'trainingDataPath', 'predictionDataPath', 'outputPath'];
  const hostRoot = process.cwd();
  
  for (const key of pathKeys) {
    if (adjusted[key] && typeof adjusted[key] === 'string') {
      const originalPath = path.resolve(adjusted[key]);
      
      // Only replace if the path starts with the host root
      if (originalPath.startsWith(hostRoot)) {
        // Convert host path to container path using proper path operations
        const relativePath = path.relative(hostRoot, originalPath);
        adjusted[key] = path.join(CONTAINER_ROOT_PATH, relativePath).replace(/\\/g, '/'); // Normalize for Unix
      } else {
        // Log warning if path doesn't match expected pattern
        console.warn(`[Docker] Path ${key} does not start with expected root: ${originalPath}`);
      }
    }
  }

  return adjusted;
}

export async function executePythonTask(options: PythonTaskOptions): Promise<void> {
  const { taskId } = options;
  
  let taskCompleted = false; // Flag to prevent race conditions
  
  try {
    // Update task status to running
    await db.update(schema.tasks)
      .set({ 
        status: 'running',
        updatedAt: new Date()
      })
      .where(eq(schema.tasks.taskId, taskId));

    // Determine execution mode
    const executionMode = getExecutionMode();
    console.log(`[${taskId}] Execution mode: ${executionMode}`);

    // Execute Python script based on mode
    const pythonProcess = executionMode === 'docker' 
      ? executeDockerPython(options)
      : executeLocalPython(options);

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
      
      // Note: comparison_result is deprecated (no longer used)
      // Evaluation metrics are now stored directly from tuning
        
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
