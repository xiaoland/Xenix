import { db, schema } from '../../database';
import { desc } from 'drizzle-orm';

export default defineEventHandler(async (event) => {
  try {
    // Fetch all datasets, ordered by most recent first
    const datasets = await db
      .select()
      .from(schema.datasets)
      .orderBy(desc(schema.datasets.createdAt));

    // Parse JSON columns field for each dataset
    const datasetsWithParsedColumns = datasets.map(dataset => ({
      ...dataset,
      columns: typeof dataset.columns === 'string' 
        ? JSON.parse(dataset.columns) 
        : dataset.columns,
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
