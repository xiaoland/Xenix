/**
 * API endpoint to synchronize model metadata from Python scripts
 * Scans the business/ml directory and updates the database with model information
 */
import { db } from '../../database';
import { modelMetadata } from '../../database/schema';
import { executePythonScript } from '../../utils/pythonExecutor';
import { eq } from 'drizzle-orm';

export default defineEventHandler(async (event) => {
  try {
    // Execute the Python model scanning script
    const scriptPath = 'server/business/ml/scan_models.py';
    const result = await executePythonScript(scriptPath, {});

    if (!result.success) {
      throw new Error(result.error || 'Model scanning failed');
    }

    const models = result.models || [];
    let syncedCount = 0;
    let updatedCount = 0;
    let errors: string[] = [];

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
        errors.push(`Failed to sync ${model.name}: ${error.message}`);
      }
    }

    return {
      success: true,
      message: 'Model metadata synchronized successfully',
      synced: syncedCount,
      updated: updatedCount,
      total: models.length,
      errors: errors.length > 0 ? errors : undefined,
    };
  } catch (error: any) {
    console.error('Failed to sync model metadata:', error);
    return {
      success: false,
      error: error.message || 'Failed to sync model metadata',
    };
  }
});
