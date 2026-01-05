import { Hono } from 'hono';
import { HTTPException } from 'hono/http-exception';
import { db, schema } from '../database/index.js';
import { desc, eq, inArray } from 'drizzle-orm';
import { authMiddleware, requireAuth } from '../middleware/auth.js';

const workItems = new Hono();
workItems.use('*', authMiddleware);

// Get all work items
workItems.get('/', async (c) => {
  try {
    const user = requireAuth(c);
    const projectId = c.req.query('projectId');

    // Get all project IDs owned by the current user
    const userProjects = await db
      .select({ id: schema.projects.id })
      .from(schema.projects)
      .where(eq(schema.projects.createdBy, user.id));

    const userProjectIds = userProjects.map((p) => p.id);

    if (userProjectIds.length === 0) {
      return c.json({
        success: true,
        workItems: [],
      });
    }

    let workItemsQuery = db.select().from(schema.workItems);

    // Filter by project if projectId is provided
    if (projectId) {
      const projectIdNum = Number(projectId);
      if (!isNaN(projectIdNum)) {
        // Check if the project belongs to the user
        if (!userProjectIds.includes(projectIdNum)) {
          throw new HTTPException(403, { message: 'Access denied' });
        }
        workItemsQuery = workItemsQuery.where(
          eq(schema.workItems.projectId, projectIdNum)
        ) as any;
      }
    } else {
      // Return work items from all user's projects
      workItemsQuery = workItemsQuery.where(
        inArray(schema.workItems.projectId, userProjectIds)
      ) as any;
    }

    const items = await workItemsQuery.orderBy(desc(schema.workItems.createdAt));

    return c.json({
      success: true,
      workItems: items,
    });
  } catch (error) {
    console.error('Work items fetch error:', error);
    if (error instanceof HTTPException) {
      throw error;
    }
    throw new HTTPException(500, {
      message:
        error instanceof Error ? error.message : 'Failed to fetch work items',
    });
  }
});

// Create work item
workItems.post('/', async (c) => {
  try {
    const user = requireAuth(c);
    const body = await c.req.json();
    const { name, description, projectId } = body;

    if (!name) {
      throw new HTTPException(400, { message: 'Work item name is required' });
    }

    if (!projectId || isNaN(Number(projectId))) {
      throw new HTTPException(400, { message: 'Valid project ID is required' });
    }

    // Verify project exists and belongs to the current user
    const projects = await db
      .select()
      .from(schema.projects)
      .where(eq(schema.projects.id, Number(projectId)))
      .limit(1);

    if (projects.length === 0) {
      throw new HTTPException(404, { message: 'Project not found' });
    }

    const project = projects[0];

    if (project.createdBy !== user.id) {
      throw new HTTPException(403, { message: 'Access denied' });
    }

    // Create work item record
    const result = await db
      .insert(schema.workItems)
      .values({
        projectId: Number(projectId),
        name,
        description: description || null,
        status: 'active',
      })
      .returning();

    const workItem = result[0];

    return c.json({
      success: true,
      workItem,
      message: 'Work item created successfully',
    });
  } catch (error) {
    console.error('Work item creation error:', error);
    if (error instanceof HTTPException) {
      throw error;
    }
    throw new HTTPException(500, {
      message:
        error instanceof Error ? error.message : 'Failed to create work item',
    });
  }
});

// Get single work item
workItems.get('/:id', async (c) => {
  try {
    const user = requireAuth(c);
    const id = parseInt(c.req.param('id'));

    if (isNaN(id)) {
      throw new HTTPException(400, { message: 'Invalid work item ID' });
    }

    const workItemsResult = await db
      .select({
        workItem: schema.workItems,
        projectCreatedBy: schema.projects.createdBy,
      })
      .from(schema.workItems)
      .innerJoin(
        schema.projects,
        eq(schema.workItems.projectId, schema.projects.id)
      )
      .where(eq(schema.workItems.id, id))
      .limit(1);

    if (workItemsResult.length === 0) {
      throw new HTTPException(404, { message: 'Work item not found' });
    }

    const { workItem, projectCreatedBy } = workItemsResult[0];

    // Check if the work item's project belongs to the current user
    if (projectCreatedBy !== user.id) {
      throw new HTTPException(403, { message: 'Access denied' });
    }

    return c.json({
      success: true,
      workItem,
    });
  } catch (error) {
    console.error('Work item fetch error:', error);
    if (error instanceof HTTPException) {
      throw error;
    }
    throw new HTTPException(500, {
      message:
        error instanceof Error ? error.message : 'Failed to fetch work item',
    });
  }
});

// Update work item
workItems.put('/:id', async (c) => {
  try {
    const user = requireAuth(c);
    const id = parseInt(c.req.param('id'));
    const body = await c.req.json();

    if (isNaN(id)) {
      throw new HTTPException(400, { message: 'Invalid work item ID' });
    }

    // Check if the work item exists and belongs to a project owned by the current user
    const workItemsResult = await db
      .select({
        workItem: schema.workItems,
        projectCreatedBy: schema.projects.createdBy,
      })
      .from(schema.workItems)
      .innerJoin(
        schema.projects,
        eq(schema.workItems.projectId, schema.projects.id)
      )
      .where(eq(schema.workItems.id, id))
      .limit(1);

    if (workItemsResult.length === 0) {
      throw new HTTPException(404, { message: 'Work item not found' });
    }

    const { workItem, projectCreatedBy } = workItemsResult[0];

    if (projectCreatedBy !== user.id) {
      throw new HTTPException(403, { message: 'Access denied' });
    }

    const updateData: any = {
      updatedAt: new Date(),
    };

    if (body.name !== undefined) {
      updateData.name = body.name;
    }
    if (body.description !== undefined) {
      updateData.description = body.description;
    }
    if (body.status !== undefined) {
      updateData.status = body.status;
    }
    // Upload step results
    if (body.datasetId !== undefined) {
      updateData.datasetId = body.datasetId ? Number(body.datasetId) : null;
    }
    if (body.featureColumns !== undefined) {
      updateData.featureColumns = body.featureColumns;
    }
    if (body.targetColumn !== undefined) {
      updateData.targetColumn = body.targetColumn;
    }
    // Tuning step results
    if (body.selectedModels !== undefined) {
      updateData.selectedModels = body.selectedModels;
    }

    await db
      .update(schema.workItems)
      .set(updateData)
      .where(eq(schema.workItems.id, id));

    return c.json({
      success: true,
      message: 'Work item updated successfully',
    });
  } catch (error) {
    console.error('Work item update error:', error);
    if (error instanceof HTTPException) {
      throw error;
    }
    throw new HTTPException(500, {
      message:
        error instanceof Error ? error.message : 'Failed to update work item',
    });
  }
});

// Delete work item
workItems.delete('/:id', async (c) => {
  try {
    const user = requireAuth(c);
    const id = parseInt(c.req.param('id'));

    if (isNaN(id)) {
      throw new HTTPException(400, { message: 'Invalid work item ID' });
    }

    // Check if the work item exists and belongs to a project owned by the current user
    const workItemsResult = await db
      .select({
        workItem: schema.workItems,
        projectCreatedBy: schema.projects.createdBy,
      })
      .from(schema.workItems)
      .innerJoin(
        schema.projects,
        eq(schema.workItems.projectId, schema.projects.id)
      )
      .where(eq(schema.workItems.id, id))
      .limit(1);

    if (workItemsResult.length === 0) {
      throw new HTTPException(404, { message: 'Work item not found' });
    }

    const { workItem, projectCreatedBy } = workItemsResult[0];

    if (projectCreatedBy !== user.id) {
      throw new HTTPException(403, { message: 'Access denied' });
    }

    // Delete work item (cascades to tasks due to FK if configured)
    await db.delete(schema.workItems).where(eq(schema.workItems.id, id));

    return c.json({
      success: true,
      message: 'Work item deleted successfully',
    });
  } catch (error) {
    console.error('Work item deletion error:', error);
    if (error instanceof HTTPException) {
      throw error;
    }
    throw new HTTPException(500, {
      message:
        error instanceof Error ? error.message : 'Failed to delete work item',
    });
  }
});

export default workItems;
