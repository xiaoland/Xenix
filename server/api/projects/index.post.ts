import { db, schema } from '../../database';

export default defineEventHandler(async (event) => {
  try {
    const body = await readBody(event);
    const { name, description } = body;

    if (!name) {
      throw createError({
        statusCode: 400,
        message: 'Project name is required',
      });
    }

    // Create project record
    const result = await db.insert(schema.projects).values({
      name,
      description: description || null,
      status: 'active',
    }).returning();

    const project = result[0];

    return {
      success: true,
      project,
      message: 'Project created successfully',
    };
  } catch (error) {
    console.error('Project creation error:', error);
    if (error && typeof error === 'object' && 'statusCode' in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to create project',
    });
  }
});
