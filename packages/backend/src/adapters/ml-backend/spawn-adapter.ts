/**
 * Spawn Adapter for ML Backend
 *
 * Invokes ml-backend by spawning local processes using the stdio adapter.
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
  AutoTuneRequest,
  ManualTuneRequest,
  PredictRequest,
} from "./interface";
import { eq } from "drizzle-orm";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface StructuredOutput {
  type: "log" | "status" | "result";
  data: any;
}

/**
 * Spawn Adapter - Invokes ml-backend by spawning Node.js processes locally
 */
export class SpawnAdapter implements MLBackendAdapter {
  private mlBackendPath: string;

  constructor() {
    // Path to ml-backend's stdio adapter entry point
    this.mlBackendPath = path.join(
      __dirname,
      "..",
      "..",
      "..",
      "..",
      "ml-backend",
      "dist",
      "adapters",
      "stdio",
      "index.js"
    );
  }

  isAvailable(): boolean {
    // Spawn adapter is always available in local environment
    return true;
  }

  async autoTune(options: AutoTuneRequest): Promise<void> {
    const operation = {
      operation: "batch-train",
      taskId: options.taskId,
      inputFile: options.inputFile,
      model: options.model,
      featureColumns: options.featureColumns,
      targetColumn: options.targetColumn,
      paramGrid: options.paramGrid || {},
      databaseUrl: process.env.DATABASE_URL,
    };

    await this.executeOperation(operation, options.taskId);
  }

  async manualTune(options: ManualTuneRequest): Promise<void> {
    const operation = {
      operation: "single-train",
      taskId: options.taskId,
      inputFile: options.inputFile,
      model: options.model,
      featureColumns: options.featureColumns,
      targetColumn: options.targetColumn,
      params: options.parameters,
      parentTaskId: options.parentTaskId,
      databaseUrl: process.env.DATABASE_URL,
    };

    await this.executeOperation(operation, options.taskId);
  }

  async predict(options: PredictRequest): Promise<void> {
    const operation = {
      operation: "predict",
      taskId: options.taskId,
      trainData: options.trainingDataPath,
      predictData: options.predictionData,
      outputPath: options.outputPath,
      model: options.model,
      params: options.params,
      featureColumns: options.featureColumns,
      targetColumn: options.targetColumn,
      databaseUrl: process.env.DATABASE_URL,
    };

    await this.executeOperation(operation, options.taskId);
  }

  /**
   * Execute an ML operation by spawning ml-backend stdio adapter
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

      // Spawn Node.js process with ml-backend stdio adapter
      const nodeProcess = spawn("node", [this.mlBackendPath], {
        stdio: ["pipe", "pipe", "pipe"],
        env: {
          ...process.env,
          NODE_ENV: process.env.NODE_ENV || "development",
        },
      });

      // Write operation JSON to stdin
      nodeProcess.stdin.write(JSON.stringify(operation));
      nodeProcess.stdin.end();

      let stdoutBuffer = "";
      let stderrBuffer = "";

      nodeProcess.stdout.on("data", async (data) => {
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

      nodeProcess.stderr.on("data", async (data) => {
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

      nodeProcess.on("close", async (code) => {
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

      nodeProcess.on("error", async (error) => {
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
          // Store log in database
          await this.storeLog(output.data, taskId);
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
            })
            .where(eq(schema.tasks.id, taskId));
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
