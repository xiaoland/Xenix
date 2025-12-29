import { db, schema } from '../../database';
import { eq } from 'drizzle-orm';
import fs from 'fs/promises';

export default defineEventHandler(async (event) => {
  const id = Number(getRouterParam(event, 'id'));

  if (isNaN(id)) {
    throw createError({
      statusCode: 400,
      message: 'Invalid dataset ID',
    });
  }

  try {
    // Fetch dataset by ID
    const [dataset] = await db
      .select()
      .from(schema.datasets)
      .where(eq(schema.datasets.id, id))
      .limit(1);

    if (!dataset) {
      throw createError({
        statusCode: 404,
        message: 'Dataset not found',
      });
    }

    // Delete the file from filesystem if it exists
    try {
      await fs.unlink(dataset.filePath);
    } catch (fileError: any) {
      // Ignore ENOENT (file not found) errors, but log others
      if (fileError.code !== 'ENOENT') {
        console.warn('Failed to delete file:', fileError);
      }
    }

    // Delete dataset record from database
    await db
      .delete(schema.datasets)
      .where(eq(schema.datasets.id, id));

    return {
      success: true,
      message: 'Dataset deleted successfully',
    };
  } catch (error) {
    console.error('Dataset deletion error:', error);
    // Re-throw createError objects directly
    if (error && typeof error === 'object' && 'statusCode' in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to delete dataset',
    });
  }
});
