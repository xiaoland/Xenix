import { db, schema } from '../../database';
import { parseDatasetColumns } from '../../utils/datasetUtils';
import { desc } from 'drizzle-orm';

export default defineEventHandler(async (event) => {
  try {
    // Fetch all datasets, ordered by most recent first
    const datasets = await db
      .select()
      .from(schema.datasets)
      .orderBy(desc(schema.datasets.createdAt));

    // Parse columns field for each dataset using utility function
    const datasetsWithParsedColumns = datasets.map(dataset => ({
      ...dataset,
      columns: parseDatasetColumns(dataset.columns),
    }));

    return {
      success: true,
      datasets: datasetsWithParsedColumns,
    };
  } catch (error) {
    console.error('Datasets fetch error:', error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to fetch datasets',
    });
  }
});
