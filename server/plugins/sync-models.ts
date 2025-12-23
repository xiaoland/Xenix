/**
 * Server plugin to synchronize model metadata on application startup
 * This ensures the model metadata table is always up-to-date with available models
 */
import { db } from '~/server/database';
import { modelMetadata } from '~/server/database/schema';
import { executePythonScript } from '~/server/utils/pythonExecutor';
import { eq } from 'drizzle-orm';

export default defineNitroPlugin(async (nitroApp) => {
  console.log('🔄 Synchronizing model metadata...');

  try {
    // Execute the Python model scanning script
    const scriptPath = 'server/business/ml/scan_models.py';
    const result = await executePythonScript(scriptPath, {});

    if (!result.success) {
      console.error('❌ Model scanning failed:', result.error);
      return;
    }

    const models = result.models || [];
    let syncedCount = 0;
    let updatedCount = 0;

    // Synchronize each model to the database
    for (const model of models) {
      try {
        // Check if model already exists
        const existing = await db
          .select()
          .from(modelMetadata)
          .where(eq(modelMetadata.name, model.name))
          .get();

        if (existing) {
          // Update existing model
          await db
            .update(modelMetadata)
            .set({
              category: model.category,
              label: model.label,
              paramGridSchema: model.param_grid_schema,
              updatedAt: new Date(),
            })
            .where(eq(modelMetadata.name, model.name))
            .run();
          updatedCount++;
        } else {
          // Insert new model
          await db
            .insert(modelMetadata)
            .values({
              category: model.category,
              name: model.name,
              label: model.label,
              paramGridSchema: model.param_grid_schema,
            })
            .run();
          syncedCount++;
        }
      } catch (error: any) {
        console.error(`❌ Failed to sync ${model.name}:`, error.message);
      }
    }

    console.log(
      `✅ Model metadata synchronized: ${syncedCount} new, ${updatedCount} updated, ${models.length} total`
    );
  } catch (error: any) {
    console.error('❌ Failed to sync model metadata on startup:', error);
  }
});
