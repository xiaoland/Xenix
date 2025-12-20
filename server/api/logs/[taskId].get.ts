import { db, schema } from '../../database';
import { eq, desc } from 'drizzle-orm';

export default defineEventHandler(async (event) => {
  const taskId = getRouterParam(event, 'taskId');

  if (!taskId) {
    throw createError({
      statusCode: 400,
      message: 'Task ID is required',
    });
  }

  try {
    // Get logs for this task (using trace_id)
    const logs = await db.select()
      .from(schema.logs)
      .where(eq(schema.logs.traceId, taskId))
      .orderBy(desc(schema.logs.timestamp))
      .limit(500); // Limit to last 500 logs

    return {
      success: true,
      logs: logs.map(log => ({
        id: log.id,
        timestamp: log.timestamp,
        severity: log.severityText,
        message: log.body,
        attributes: log.attributes,
        createdAt: log.createdAt,
      })),
    };
  } catch (error) {
    console.error('Logs fetch error:', error);
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to fetch logs',
    });
  }
});
