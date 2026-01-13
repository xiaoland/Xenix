/**
 * Model Service
 * Business logic for model metadata operations
 */
import { eq } from 'drizzle-orm';

import { db, schema } from '../database/index.js';
import { NotFoundError } from '../errors/index.js';
import { syncModelMetadata } from '../utils/syncModels.js';

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
    return await syncModelMetadata();
  }
}
