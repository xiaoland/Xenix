import { Hono } from "hono";
import { HTTPException } from "hono/http-exception";
import { db, schema } from "../database/index.js";
import { eq } from "drizzle-orm";
import { authMiddleware } from "../middleware/auth.js";
import { autoTune, manualTune } from "../business/ml/index.js";

const tune = new Hono()
  .use("*", authMiddleware)

  // Auto-tune endpoint
  .post("/auto-tune", async (c) => {
    try {
      const body = await c.req.json();
      let { datasetId, features, target, model, paramGrid, workItemId } = body;

      // If workItemId provided, try to fill missing values from the work item
      if (workItemId) {
        const [workItem] = await db
          .select()
          .from(schema.workItems)
          .where(eq(schema.workItems.id, Number(workItemId)))
          .limit(1);

        if (workItem) {
          if (!datasetId && workItem.datasetId) datasetId = workItem.datasetId;
          if (
            (!features || (Array.isArray(features) && features.length === 0)) &&
            workItem.featureColumns
          ) {
            features = Array.isArray(workItem.featureColumns)
              ? workItem.featureColumns
              : JSON.parse(workItem.featureColumns as any);
          }
          if (!target && workItem.targetColumn)
            target = workItem.targetColumn as any;
        }
      }

      // Validate required parameters (after trying to fill from work item)
      if (!datasetId) {
        throw new HTTPException(400, { message: "datasetId is required" });
      }

      if (!model) {
        throw new HTTPException(400, { message: "model is required" });
      }

      if (!features || !Array.isArray(features) || features.length === 0) {
        throw new HTTPException(400, {
          message: "features array is required and must not be empty",
        });
      }

      if (!target) {
        throw new HTTPException(400, { message: "target is required" });
      }

      // Verify dataset exists
      const [dataset] = await db
        .select()
        .from(schema.datasets)
        .where(eq(schema.datasets.id, Number(datasetId)))
        .limit(1);

      if (!dataset) {
        throw new HTTPException(404, { message: "Dataset not found" });
      }

      // Create task record with auto-tune type
      const [insertedTask] = await db
        .insert(schema.tasks)
        .values({
          workItemId: workItemId ? Number(workItemId) : null,
          type: "auto-tune",
          status: "pending",
          parameter: {
            model,
            datasetId,
            featureColumns: features,
            targetColumn: target,
            paramGrid,
            trainingType: "auto",
          },
        })
        .returning();

      const taskId = insertedTask.id;

      // Execute tuning task in background
      setImmediate(() => {
        autoTune({
          inputFile: dataset.filePath,
          model,
          featureColumns: features,
          targetColumn: target,
          taskId,
          paramGrid,
        }).catch((error) => {
          console.error(`Failed to execute tune task ${taskId}:`, error);
        });
      });

      return c.json({
        success: true,
        taskId,
        message: "Auto-tune started",
      });
    } catch (error) {
      console.error("Tune error:", error);
      if (error instanceof HTTPException) {
        throw error;
      }
      throw new HTTPException(500, {
        message:
          error instanceof Error ? error.message : "Failed to start tuning",
      });
    }
  })

  // Manual-tune endpoint
  .post("/manual-tune", async (c) => {
    try {
      const body = await c.req.json();
      let { datasetId, features, target, model, parameters, workItemId } = body;

      // If workItemId provided, try to fill missing values from the work item
      if (workItemId) {
        const [workItem] = await db
          .select()
          .from(schema.workItems)
          .where(eq(schema.workItems.id, Number(workItemId)))
          .limit(1);

        if (workItem) {
          if (!datasetId && workItem.datasetId) datasetId = workItem.datasetId;
          if (
            (!features || (Array.isArray(features) && features.length === 0)) &&
            workItem.featureColumns
          ) {
            features = Array.isArray(workItem.featureColumns)
              ? workItem.featureColumns
              : JSON.parse(workItem.featureColumns as any);
          }
          if (!target && workItem.targetColumn)
            target = workItem.targetColumn as any;
        }
      }

      // Validate required parameters (after trying to fill from work item)
      if (!datasetId) {
        throw new HTTPException(400, { message: "datasetId is required" });
      }

      if (!model) {
        throw new HTTPException(400, { message: "model is required" });
      }

      if (!features || !Array.isArray(features) || features.length === 0) {
        throw new HTTPException(400, {
          message: "features array is required and must not be empty",
        });
      }

      if (!target) {
        throw new HTTPException(400, { message: "target is required" });
      }

      if (!parameters) {
        throw new HTTPException(400, {
          message: "parameters object is required",
        });
      }

      // Verify dataset exists
      const [dataset] = await db
        .select()
        .from(schema.datasets)
        .where(eq(schema.datasets.id, Number(datasetId)))
        .limit(1);

      if (!dataset) {
        throw new HTTPException(404, { message: "Dataset not found" });
      }

      // Create task record with manual-tune type
      const [insertedTask] = await db
        .insert(schema.tasks)
        .values({
          workItemId: workItemId ? Number(workItemId) : null,
          type: "manual-tune",
          status: "pending",
          parameter: {
            model,
            datasetId,
            featureColumns: features,
            targetColumn: target,
            parameters,
            trainingType: "manual",
          },
        })
        .returning();

      const taskId = insertedTask.id;

      // Execute training task in background
      setImmediate(() => {
        manualTune({
          inputFile: dataset.filePath,
          model,
          featureColumns: features,
          targetColumn: target,
          taskId,
          parameters,
        }).catch((error) => {
          console.error(`Failed to execute manual tune task ${taskId}:`, error);
        });
      });

      return c.json({
        success: true,
        taskId,
        message: "Manual tuning started",
      });
    } catch (error) {
      console.error("Manual tune error:", error);
      if (error instanceof HTTPException) {
        throw error;
      }
      throw new HTTPException(500, {
        message:
          error instanceof Error
            ? error.message
            : "Failed to start manual tuning",
      });
    }
  });

export default tune;
