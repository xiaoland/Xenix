import { db, schema } from '../../database';
import { nanoid } from 'nanoid';

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

    // Generate project ID
    const projectId = `proj_${nanoid(10)}`;

    // Create project record
    await db.insert(schema.projects).values({
      projectId,
      name,
      description: description || null,
      datasetIds: [],
      workItemIds: [],
      status: 'active',
    });

    return {
      success: true,
      project: {
        projectId,
        name,
        description,
        datasetIds: [],
        workItemIds: [],
        status: 'active',
      },
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
