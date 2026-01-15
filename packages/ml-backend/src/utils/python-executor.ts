import { spawn } from 'child_process';
import path from 'path';
import type {
  PythonExecutorOptions,
  StructuredOutput,
  StructuredLog,
} from '../types';

/**
 * Execute a Python script with structured input/output
 * This is a generic executor that doesn't depend on database or task management
 */
export async function executePython<T = any>(
  options: PythonExecutorOptions
): Promise<T> {
  const { script, stdinData, cwd, onLog, onResult } = options;

  return new Promise((resolve, reject) => {
    // Use python3 explicitly or from environment variable
    const pythonCmd = (process.env.PYTHON_EXECUTABLE || 'python3').replace(
      /\\/g,
      '/'
    );

    // Determine the Python path - if script is absolute, use it; otherwise, resolve relative to cwd
    const scriptPath = path.isAbsolute(script)
      ? script
      : path.join(cwd || process.cwd(), script);

    // Execute Python script (no CLI args, use stdin instead)
    const pythonProcess = spawn(pythonCmd, [scriptPath], {
      cwd: cwd || process.cwd(),
      env: {
        ...process.env,
        PYTHONPATH: process.env.PYTHONPATH || '',
        PATH: `${path.dirname(process.env.PYTHON_EXECUTABLE || 'python3')}${path.delimiter}${process.env.PATH}`,
      },
      shell: process.platform === 'win32', // Use shell on Windows
    });

    // Write JSON data to stdin
    if (stdinData) {
      pythonProcess.stdin.write(JSON.stringify(stdinData));
      pythonProcess.stdin.end();
    }

    let stdoutBuffer = '';
    let stderrBuffer = '';
    let result: T | null = null;

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
            await handleStructuredOutput(parsed, { onLog, onResult });

            // Store result if this is the result line
            if (parsed.type === 'result') {
              result = parsed.data as T;
            }
          } catch {
            // Not JSON, ignore or log to console
            if (process.env.DEBUG) {
              console.log(`[Python stdout]: ${line}`);
            }
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
            await handleStructuredOutput(parsed, { onLog, onResult });
          } catch {
            // Not JSON, accumulate as error
            if (process.env.DEBUG) {
              console.error(`[Python stderr]: ${line}`);
            }
          }
        }
      }
    });

    pythonProcess.on('close', (code) => {
      if (code === 0) {
        // Task completed successfully
        if (result !== null) {
          resolve(result);
        } else {
          reject(new Error('Python script completed but no result was returned'));
        }
      } else {
        // Task failed
        reject(
          new Error(
            `Python script failed with code ${code}: ${stderrBuffer || 'Unknown error'}`
          )
        );
      }
    });

    pythonProcess.on('error', (error) => {
      reject(new Error(`Failed to start Python script: ${error.message}`));
    });
  });
}

/**
 * Handle structured output from Python scripts
 */
async function handleStructuredOutput(
  output: StructuredOutput,
  handlers: {
    onLog?: (log: StructuredLog) => Promise<void>;
    onResult?: (result: any) => Promise<void>;
  }
) {
  try {
    switch (output.type) {
      case 'log':
        if (handlers.onLog) {
          await handlers.onLog(output.data as StructuredLog);
        }
        break;

      case 'result':
        if (handlers.onResult) {
          await handlers.onResult(output.data);
        }
        break;

      case 'status':
        // Status updates can be handled by onLog if needed
        if (handlers.onLog && output.data.message) {
          await handlers.onLog({
            timestamp: Date.now() * 1000000,
            observed_timestamp: Date.now() * 1000000,
            severity_text: 'INFO',
            severity_number: 9,
            body: output.data.message,
            attributes: output.data,
          } as StructuredLog);
        }
        break;
    }
  } catch (error) {
    console.error('Error handling structured output:', error);
  }
}

/**
 * Execute a Python script synchronously and return the raw JSON result
 * Used for simple scripts that don't need structured logging (like model scanning)
 */
export async function executePythonSync<T = any>(
  scriptPath: string,
  stdinData: any,
  cwd?: string
): Promise<T> {
  return new Promise((resolve, reject) => {
    const pythonCmd = (process.env.PYTHON_EXECUTABLE || 'python3').replace(
      /\\/g,
      '/'
    );

    const fullScriptPath = path.isAbsolute(scriptPath)
      ? scriptPath
      : path.join(cwd || process.cwd(), scriptPath);

    const pythonProcess = spawn(pythonCmd, [fullScriptPath], {
      cwd: cwd || process.cwd(),
      env: {
        ...process.env,
        PYTHONPATH: process.env.PYTHONPATH || '',
        PATH: `${path.dirname(process.env.PYTHON_EXECUTABLE || 'python3')}${path.delimiter}${process.env.PATH}`,
      },
      shell: process.platform === 'win32',
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
        reject(
          new Error(`Python script failed with code ${code}: ${stderrBuffer}`)
        );
      }
    });

    pythonProcess.on('error', (error) => {
      reject(new Error(`Failed to execute Python script: ${error.message}`));
    });
  });
}
