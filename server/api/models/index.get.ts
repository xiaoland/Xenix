/**
 * API endpoint to retrieve all model metadata from database
 */
import { db } from '../../database';
import { modelMetadata } from '../../database/schema';

export default defineEventHandler(async (event) => {
  try {
    const models = await db.select().from(modelMetadata).all();

    return {
      success: true,
      models,
      count: models.length,
    };
  } catch (error: any) {
    console.error('Failed to fetch model metadata:', error);
    return {
      success: false,
      error: error.message || 'Failed to fetch model metadata',
    };
  }
});
