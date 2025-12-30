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
