import { db, schema } from '../../database';
import { eq } from 'drizzle-orm';
import fs from 'fs/promises';

export default defineEventHandler(async (event) => {
  const datasetId = getRouterParam(event, 'id');

  if (!datasetId) {
    throw createError({
      statusCode: 400,
      message: 'Dataset ID is required',
    });
  }

  try {
    // Fetch dataset by ID
    const [dataset] = await db
      .select()
      .from(schema.datasets)
      .where(eq(schema.datasets.datasetId, datasetId))
      .limit(1);

    if (!dataset) {
      throw createError({
        statusCode: 404,
        message: 'Dataset not found',
      });
    }

    // Delete the file from filesystem if it exists
    try {
      await fs.access(dataset.filePath);
      await fs.unlink(dataset.filePath);
    } catch (fileError) {
      // File doesn't exist or can't be accessed, continue with database deletion
      console.warn('File not found or cannot be accessed:', fileError);
    }

    // Delete dataset record from database
    await db
      .delete(schema.datasets)
      .where(eq(schema.datasets.datasetId, datasetId));

    return {
      success: true,
      message: 'Dataset deleted successfully',
    };
  } catch (error) {
    console.error('Dataset deletion error:', error);
    throw createError({
      statusCode: error.statusCode || 500,
      message: error instanceof Error ? error.message : 'Failed to delete dataset',
    });
  }
});
