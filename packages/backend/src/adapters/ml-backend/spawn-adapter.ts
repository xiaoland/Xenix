/**
 * Spawn Adapter for ML Backend
 *
 * Invokes ml-backend by spawning Python processes using stdio.
 * Used for local development.
 *
 * I/O Characteristics:
 * - Requires full local file paths
 * - Results are captured from stdout and updated to database by backend
 * - Logs are parsed from stdout and stored in database
 */

import { spawn } from "child_process";
import path from "path";
import { fileURLToPath } from "url";

import { db, schema } from "../../database";
import logger from "../../utils/logger";
import { generateTraceId } from "../../utils/taskUtils";
import type {
  MLBackendAdapter,
  BatchTrainRequest,
  SingleTrainRequest,
  PredictRequest,
} from "./interface";
import type { SpawnAdapterParams } from "../../types/ml-backend";
import { eq } from "drizzle-orm";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface StructuredOutput {
  type: "log" | "status" | "result" | "error";
  data?: any;
  error?: string;
  traceback?: string;
}

/**
 * Spawn Adapter - Invokes ml-backend by spawning Python processes locally
 */
export class SpawnAdapter implements MLBackendAdapter {
  private pythonPath: string;
  private mlBackendPath: string;
  private basePath?: string;

  constructor(params: SpawnAdapterParams = {}) {
    this.pythonPath = params.pythonPath || "python3";
    this.mlBackendPath =
      params.mlBackendPath || this.detectMLBackendPath();
    this.basePath = params.basePath;
  }

  /**
   * Auto-detect ml-backend main.py path
   */
  private detectMLBackendPath(): string {
    return path.join(
      __dirname,
      "..",
      "..",
      "..",
      "..",
      "ml-backend",
      "main.py"
    );
  }

  isAvailable(): boolean {
    // Spawn adapter is always available in local environment
    return true;
  }

  async batchTrain(options: BatchTrainRequest): Promise<void> {
    const operation = {
      operation: "batch-train",
      data: {
        task_id: options.taskId,
        input_file: options.inputFile,
        model: options.model,
        feature_columns: options.featureColumns,
        target_column: options.targetColumn,
        param_grid: options.paramGrid || {},
      },
    };

    await this.executeOperation(operation, options.taskId);
  }

  async singleTrain(options: SingleTrainRequest): Promise<void> {
    const operation = {
      operation: "single-train",
      data: {
        task_id: options.taskId,
        input_file: options.inputFile,
        model: options.model,
        feature_columns: options.featureColumns,
        target_column: options.targetColumn,
        parameters: options.parameters,
        parent_task_id: options.parentTaskId,
      },
    };

    await this.executeOperation(operation, options.taskId);
  }

  async predict(options: PredictRequest): Promise<void> {
    const operation = {
      operation: "predict",
      data: {
        task_id: options.taskId,
        training_data_path: options.trainingDataPath,
        prediction_data: options.predictionData,
        output_path: options.outputPath,
        model: options.model,
        parameters: options.params,
        feature_columns: options.featureColumns,
        target_column: options.targetColumn,
      },
    };

    await this.executeOperation(operation, options.taskId);
  }

  /**
   * Execute an ML operation by spawning Python ml-backend
   */
  private async executeOperation(
    operation: any,
    taskId: number
  ): Promise<void> {
    const traceId = generateTraceId(taskId);
    let taskCompleted = false;

    try {
      // Update task status to running
      await db
        .update(schema.tasks)
        .set({
          status: "running",
          startedAt: new Date(),
        })
        .where(eq(schema.tasks.id, taskId));

      // Build Python command arguments
      const pythonArgs = [this.mlBackendPath];

      // Add --base-path argument if configured
      if (this.basePath) {
        pythonArgs.push("--base-path", this.basePath);
      }

      // Spawn Python process with ml-backend
      const pythonProcess = spawn(this.pythonPath, pythonArgs, {
        stdio: ["pipe", "pipe", "pipe"],
        env: {
          ...process.env,
          DATABASE_URL: process.env.DATABASE_URL,
        },
      });

      // Write operation JSON to stdin
      pythonProcess.stdin.write(JSON.stringify(operation));
      pythonProcess.stdin.end();

      let stdoutBuffer = "";
      let stderrBuffer = "";

      pythonProcess.stdout.on("data", async (data) => {
        const output = data.toString();
        stdoutBuffer += output;

        // Process line by line
        const lines = stdoutBuffer.split("\n");
        stdoutBuffer = lines.pop() || "";

        for (const line of lines) {
          if (line.trim()) {
            try {
              const parsed: StructuredOutput = JSON.parse(line);
              await this.handleStructuredOutput(parsed, taskId);
            } catch {
              logger.info({ traceId, line }, "ML stdout");
            }
          }
        }
      });

      pythonProcess.stderr.on("data", async (data) => {
        const output = data.toString();
        stderrBuffer += output;

        const lines = stderrBuffer.split("\n");
        stderrBuffer = lines.pop() || "";

        for (const line of lines) {
          if (line.trim()) {
            try {
              const parsed: StructuredOutput = JSON.parse(line);
              await this.handleStructuredOutput(parsed, taskId);
            } catch {
              logger.error({ traceId, line }, "ML stderr");
            }
          }
        }
      });

      pythonProcess.on("close", async (code) => {
        if (taskCompleted) return;
        taskCompleted = true;

        if (code === 0) {
          await db
            .update(schema.tasks)
            .set({
              status: "completed",
              endAt: new Date(),
            })
            .where(eq(schema.tasks.id, taskId));

          logger.info({ traceId }, "ML task completed successfully");
        } else {
          await db
            .update(schema.tasks)
            .set({
              status: "failed",
              error: stderrBuffer || `Process exited with code ${code}`,
              endAt: new Date(),
            })
            .where(eq(schema.tasks.id, taskId));

          logger.error({ traceId, exitCode: code }, "ML task failed");
        }
      });

      pythonProcess.on("error", async (error) => {
        if (taskCompleted) return;
        taskCompleted = true;

        await db
          .update(schema.tasks)
          .set({
            status: "failed",
            error: error.message,
            endAt: new Date(),
          })
          .where(eq(schema.tasks.id, taskId));

        logger.error({ traceId, error }, "Failed to start ML task");
      });
    } catch (error) {
      if (taskCompleted) return;
      taskCompleted = true;

      await db
        .update(schema.tasks)
        .set({
          status: "failed",
          error: error instanceof Error ? error.message : "Unknown error",
          endAt: new Date(),
        })
        .where(eq(schema.tasks.id, taskId));

      throw error;
    }
  }

  /**
   * Handle structured output from ml-backend
   */
  private async handleStructuredOutput(
    output: StructuredOutput,
    taskId: number
  ): Promise<void> {
    const traceId = generateTraceId(taskId);

    try {
      switch (output.type) {
        case "log":
          // Store log in database (if output.data is structured log)
          if (output.data) {
            await this.storeLog(output.data, taskId);
          }
          break;

        case "status":
          // Update task status
          await db
            .update(schema.tasks)
            .set({
              status: output.data.status,
              error: output.data.error || null,
            })
            .where(eq(schema.tasks.id, taskId));
          break;

        case "result":
          // Store result in database
          await db
            .update(schema.tasks)
            .set({
              result: output.data,
              status: "completed",
              endAt: new Date(),
            })
            .where(eq(schema.tasks.id, taskId));
          break;

        case "error":
          // Handle error output from Python ml-backend
          await db
            .update(schema.tasks)
            .set({
              status: "failed",
              error: output.error || "Unknown error",
              endAt: new Date(),
            })
            .where(eq(schema.tasks.id, taskId));

          logger.error({ traceId, error: output.error }, "ML task error");
          break;
      }
    } catch (error) {
      logger.error({ traceId, error }, "Error handling structured output");
    }
  }

  /**
   * Store log entry in database
   */
  private async storeLog(logData: any, taskId: number): Promise<void> {
    const traceId = generateTraceId(taskId);

    try {
      await db.insert(schema.logs).values({
        timestamp: logData.timestamp,
        observedTimestamp: logData.observed_timestamp,
        traceId: traceId,
        spanId: logData.span_id || null,
        severityText: logData.severity_text,
        severityNumber: logData.severity_number,
        body: logData.body,
        resource: logData.resource || null,
        attributes: logData.attributes || null,
        createdAt: new Date(),
      });
    } catch (error) {
      logger.error({ traceId, error }, "Error storing log");
    }
  }
}
