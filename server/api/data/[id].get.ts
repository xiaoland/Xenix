import { db, schema } from '../../../database';
import { eq } from 'drizzle-orm';

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

    // Parse JSON columns field
    const datasetWithParsedColumns = {
      ...dataset,
      columns: typeof dataset.columns === 'string' 
        ? JSON.parse(dataset.columns) 
        : dataset.columns,
    };

    return {
      success: true,
      dataset: datasetWithParsedColumns,
    };
  } catch (error) {
    console.error('Dataset fetch error:', error);
    throw createError({
      statusCode: error.statusCode || 500,
      message: error instanceof Error ? error.message : 'Failed to fetch dataset',
    });
  }
});
