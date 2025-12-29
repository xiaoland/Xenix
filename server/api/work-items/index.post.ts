import { db, schema } from '../../database';
import { nanoid } from 'nanoid';
import { eq } from 'drizzle-orm';
import { safeParseJsonArray } from '../../utils/datasetUtils';

export default defineEventHandler(async (event) => {
  try {
    const body = await readBody(event);
    const { name, description, projectId } = body;

    if (!name) {
      throw createError({
        statusCode: 400,
        message: 'Work item name is required',
      });
    }

    if (!projectId) {
      throw createError({
        statusCode: 400,
        message: 'Project ID is required',
      });
    }

    // Verify project exists
    const projects = await db
      .select()
      .from(schema.projects)
      .where(eq(schema.projects.projectId, projectId))
      .limit(1);

    if (projects.length === 0) {
      throw createError({
        statusCode: 404,
        message: 'Project not found',
      });
    }

    // Generate work item ID
    const workItemId = `work_${nanoid(10)}`;

    // Create work item record
    await db.insert(schema.workItems).values({
      workItemId,
      name,
      description: description || null,
      projectId,
      taskIds: [],
      status: 'active',
    });

    // Update project to include this work item
    const project = projects[0];
    const currentWorkItemIds = safeParseJsonArray(project.workItemIds, []);
    
    await db
      .update(schema.projects)
      .set({
        workItemIds: [...currentWorkItemIds, workItemId],
        updatedAt: new Date(),
      })
      .where(eq(schema.projects.projectId, projectId));

    return {
      success: true,
      workItem: {
        workItemId,
        name,
        description,
        projectId,
        taskIds: [],
        status: 'active',
      },
      message: 'Work item created successfully',
    };
  } catch (error) {
    console.error('Work item creation error:', error);
    if (error && typeof error === 'object' && 'statusCode' in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Failed to create work item',
    });
  }
});
