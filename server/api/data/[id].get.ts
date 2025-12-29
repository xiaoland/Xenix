import { db, schema } from '../../database';
import { parseDatasetColumns } from '../../utils/datasetUtils';
import { eq } from 'drizzle-orm';

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

    // Parse columns field using utility function
    const datasetWithParsedColumns = {
      ...dataset,
      columns: parseDatasetColumns(dataset.columns),
    };

    return {
      success: true,
      dataset: datasetWithParsedColumns,
    };
  } catch (error) {
    console.error('Dataset fetch error:', error);
    // Re-throw createError objects directly
    if (error && typeof error === 'object' && 'statusCode' in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to fetch dataset',
    });
  }
});
