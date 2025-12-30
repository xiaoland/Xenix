import { db, schema } from "../database";
import { train } from "../business/ml";
import { eq } from "drizzle-orm";

/**
 * API endpoint for manual tuning with specific parameters
 * Parameters: datasetId, features, target, model, parameters
 */
export default defineEventHandler(async (event) => {
  try {
    const body = await readBody(event);
    const { datasetId, features, target, model, parameters, workItemId } = body;

    // Validate required parameters
    if (!datasetId) {
      throw createError({
        statusCode: 400,
        message: "datasetId is required",
      });
    }

    if (!model) {
      throw createError({
        statusCode: 400,
        message: "model is required",
      });
    }

    if (!features || !Array.isArray(features) || features.length === 0) {
      throw createError({
        statusCode: 400,
        message: "features array is required and must not be empty",
      });
    }

    if (!target) {
      throw createError({
        statusCode: 400,
        message: "target is required",
      });
    }

    if (!parameters) {
      throw createError({
        statusCode: 400,
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
      throw createError({
        statusCode: 404,
        message: "Dataset not found",
      });
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
      train({
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

    return {
      success: true,
      taskId,
      message: "Manual tuning started",
    };
  } catch (error) {
    console.error("Manual tune error:", error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : "Failed to start manual tuning",
    });
  }
});
