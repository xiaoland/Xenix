/**
 * Utility function to synchronize model metadata
 * This ensures the model metadata table is up-to-date with available models
 */
import { eq } from "drizzle-orm";

import { db } from "../database";
import { modelMetadata } from "../database/schema";
import logger from "./logger";
import { executePythonScript } from "./pythonExecutor";

export async function syncModelMetadata() {
  logger.info("Synchronizing model metadata...");

  try {
    // Execute the Python model scanning script
    const scriptPath = "src/business/ml/scan_models.py";
    const result = await executePythonScript(scriptPath, {});

    if (!result.success) {
      logger.error({ error: result.error }, "Model scanning failed");
      throw new Error(`Model scanning failed: ${result.error}`);
    }

    const models = result.models || [];
    let syncedCount = 0;
    let updatedCount = 0;

    // Synchronize each model to the database
    for (const model of models) {
      try {
        // Check if model already exists
        const [existing] = await db
          .select()
          .from(modelMetadata)
          .where(eq(modelMetadata.name, model.name))
          .limit(1);

        if (existing) {
          // Update existing model
          await db
            .update(modelMetadata)
            .set({
              category: model.category,
              label: model.label,
              paramSchema: model.param_schema,
              paramGridSchema: model.param_grid_schema,
              updatedAt: new Date(),
            })
            .where(eq(modelMetadata.name, model.name));
          updatedCount++;
        } else {
          // Insert new model
          await db.insert(modelMetadata).values({
            category: model.category,
            name: model.name,
            label: model.label,
            paramGridSchema: model.param_grid_schema,
            paramSchema: model.param_schema,
          });
          syncedCount++;
        }
      } catch (error: any) {
        logger.error({ error, modelName: model.name }, "Failed to sync model");
      }
    }

    const message = `Model metadata synchronized: ${syncedCount} new, ${updatedCount} updated, ${models.length} total`;
    logger.info({ syncedCount, updatedCount, total: models.length }, message);
    return {
      success: true,
      syncedCount,
      updatedCount,
      total: models.length,
      message,
    };
  } catch (error: any) {
    logger.error({ error }, "Failed to sync model metadata");
    throw error;
  }
}
