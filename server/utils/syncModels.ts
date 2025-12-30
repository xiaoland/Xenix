/**
 * Utility function to synchronize model metadata
 * This ensures the model metadata table is up-to-date with available models
 */
import { db } from "../database";
import { modelMetadata } from "../database/schema";
import { executePythonScript } from "./pythonExecutor";
import { eq } from "drizzle-orm";

export async function syncModelMetadata() {
  console.log("🔄 Synchronizing model metadata...");

  try {
    // Execute the Python model scanning script
    const scriptPath = "server/business/ml/scan_models.py";
    const result = await executePythonScript(scriptPath, {});

    if (!result.success) {
      console.error("❌ Model scanning failed:", result.error);
      throw new Error(`Model scanning failed: ${result.error}`);
    }

    const models = result.models || [];
    let syncedCount = 0;
    let updatedCount = 0;

    // Synchronize each model to the database
    for (const model of models) {
      try {
        // Check if model already exists
        const existing = db
          .select()
          .from(modelMetadata)
          .where(eq(modelMetadata.name, model.name))
          .get();

        if (existing) {
          // Update existing model
          db.update(modelMetadata)
            .set({
              category: model.category,
              label: model.label,
              paramSchema: model.param_schema,
              paramGridSchema: model.param_grid_schema,
              updatedAt: new Date(),
            })
            .where(eq(modelMetadata.name, model.name))
            .run();
          updatedCount++;
        } else {
          // Insert new model
          db.insert(modelMetadata)
            .values({
              category: model.category,
              name: model.name,
              label: model.label,
              paramGridSchema: model.param_grid_schema,
              paramSchema: model.param_schema,
            })
            .run();
          syncedCount++;
        }
      } catch (error: any) {
        console.error(`❌ Failed to sync ${model.name}:`, error.message);
      }
    }

    const message = `✅ Model metadata synchronized: ${syncedCount} new, ${updatedCount} updated, ${models.length} total`;
    console.log(message);
    return {
      success: true,
      syncedCount,
      updatedCount,
      total: models.length,
      message,
    };
  } catch (error: any) {
    console.error("❌ Failed to sync model metadata:", error);
    throw error;
  }
}
