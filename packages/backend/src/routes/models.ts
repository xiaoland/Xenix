import { eq } from 'drizzle-orm';

import { zValidator } from '@hono/zod-validator';
import { Hono } from 'hono';

import { ModelIdParamSchema } from '@xenix/shared';

import { db, schema } from '../database/index.js';
import { BadRequestError, NotFoundError } from '../errors/index.js';
import { authMiddleware } from '../middleware/auth.js';
import logger from '../utils/logger/index.js';
import { executePythonScript } from '../utils/pythonExecutor.js';

const models = new Hono()
  .use('*', authMiddleware)

  // Get all models
  .get('/', async (c) => {
    const modelsList = await db.select().from(schema.modelMetadata);
    return c.json(modelsList);
  })

  // Get single model by name
  .get('/:id', zValidator('param', ModelIdParamSchema), async (c) => {
    const { id } = c.req.valid('param');

    const [model] = await db
      .select()
      .from(schema.modelMetadata)
      .where(eq(schema.modelMetadata.name, id))
      .limit(1);

    if (!model) {
      throw new NotFoundError('Model');
    }

    return c.json(model);
  })

  // Sync model metadata
  .post('/sync', async (c) => {
    // Execute the Python model scanning script
    const scriptPath = 'src/business/ml/scan_models.py';
    const result = await executePythonScript(scriptPath, {});

    if (!result.success) {
      throw new Error(result.error || 'Model scanning failed');
    }

    const modelsList = result.models || [];
    let syncedCount = 0;
    let updatedCount = 0;
    const errors: string[] = [];

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

    return c.json({
      message: 'Model metadata synchronized successfully',
      synced: syncedCount,
      updated: updatedCount,
      total: modelsList.length,
      errors: errors.length > 0 ? errors : undefined,
    });
  });

export default models;
