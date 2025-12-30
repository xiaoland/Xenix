import { db, schema } from "../database";
import { autoTune } from "../business/ml";
import { eq } from "drizzle-orm";

/**
 * API endpoint for auto-tuning models with parameter grid search
 * Parameters: datasetId, features, target, model, paramGrid
 */
export default defineEventHandler(async (event) => {
  try {
    const body = await readBody(event);
    const { datasetId, features, target, model, paramGrid, workItemId } = body;

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

    return {
      success: true,
      taskId,
      message: "Auto-tune started",
    };
  } catch (error) {
    console.error("Tune error:", error);
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error ? error.message : "Failed to start tuning",
    });
  }
});
