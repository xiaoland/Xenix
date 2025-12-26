import { db, schema } from '../../../database';
import { eq, and } from 'drizzle-orm';

/**
 * API endpoint to fetch all training history for a specific model
 * Includes both auto-tune results and manual training results
 */
export default defineEventHandler(async (event) => {
  try {
    const model = getRouterParam(event, 'model');

    if (!model) {
      throw createError({
        statusCode: 400,
        message: 'Model name is required',
      });
    }

    // Fetch all results for this model, ordered by creation time
    const results = await db
      .select()
      .from(schema.modelResults)
      .where(eq(schema.modelResults.model, model))
      .orderBy(schema.modelResults.createdAt)
      .all();

    return {
      success: true,
      results,
      count: results.length,
    };
  } catch (error) {
    console.error('Training history fetch error:', error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to fetch training history',
    });
  }
});
