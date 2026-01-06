/**
 * Model Service
 * Business logic for model metadata operations
 */

import { db, schema } from '../database/index.js';
import { eq } from 'drizzle-orm';
import { NotFoundError } from '../errors/index.js';
import { executePythonScript } from '../utils/pythonExecutor.js';
import logger from '../utils/logger/index.js';

export class ModelService {
  async getAllModels() {
    return await db.select().from(schema.modelMetadata);
  }

  async getModelByName(name: string) {
    const [model] = await db
      .select()
      .from(schema.modelMetadata)
      .where(eq(schema.modelMetadata.name, name))
      .limit(1);

    if (!model) {
      throw new NotFoundError('Model');
    }

    return model;
  }

  async syncModels() {
    // Execute the Python model scanning script
    const scriptPath = 'src/business/ml/scan_models.py';
    const result = await executePythonScript(scriptPath, {});

    if (!result.success) {
      throw new Error(result.error || 'Model scanning failed');
    }

    const modelsList = result.models || [];
    let syncedCount = 0;
    let updatedCount = 0;
    let errors: string[] = [];

    // Synchronize each model to the database
    for (const model of modelsList) {
      try {
        // Check if model already exists
        const [existing] = await db
          .select()
          .from(schema.modelMetadata)
          .where(eq(schema.modelMetadata.name, model.name))
          .limit(1);

        if (existing) {
          // Update existing model
          await db
            .update(schema.modelMetadata)
            .set({
              category: model.category,
              label: model.label,
              paramGridSchema: model.param_grid_schema,
              updatedAt: new Date(),
            })
            .where(eq(schema.modelMetadata.name, model.name));
          updatedCount++;
        } else {
          // Insert new model
          await db.insert(schema.modelMetadata).values({
            category: model.category,
            name: model.name,
            label: model.label,
            paramGridSchema: model.param_grid_schema,
          });
          syncedCount++;
        }
      } catch (error: any) {
        errors.push(`Failed to sync ${model.name}: ${error.message}`);
        logger.error({ error, modelName: model.name }, 'Failed to sync model');
      }
    }

    return {
      message: 'Model metadata synchronized successfully',
      synced: syncedCount,
      updated: updatedCount,
      total: modelsList.length,
      errors: errors.length > 0 ? errors : undefined,
    };
  }
}
