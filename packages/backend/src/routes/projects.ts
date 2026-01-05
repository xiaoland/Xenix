import { Hono } from 'hono';
import { HTTPException } from 'hono/http-exception';
import { db, schema } from '../database/index.js';
import { desc, eq } from 'drizzle-orm';
import { authMiddleware, requireAuth } from '../middleware/auth.js';

const projects = new Hono();

// Apply auth middleware to all routes
projects.use('*', authMiddleware);

// Get all projects
projects.get('/', async (c) => {
  try {
    const user = requireAuth(c);

    // Fetch projects created by the current user
    const projectsList = await db
      .select()
      .from(schema.projects)
      .where(eq(schema.projects.createdBy, user.id))
      .orderBy(desc(schema.projects.createdAt));

    // For each project, fetch its work items and datasets
    const projectsWithRelations = await Promise.all(
      projectsList.map(async (project) => {
        const workItems = await db
          .select()
          .from(schema.workItems)
          .where(eq(schema.workItems.projectId, project.id));

        const datasets = await db
          .select()
          .from(schema.datasets)
          .where(eq(schema.datasets.projectId, project.id));

        return {
          ...project,
          workItems,
          datasets,
        };
      })
    );

    return c.json({
      success: true,
      projects: projectsWithRelations,
    });
  } catch (error) {
    console.error('Projects fetch error:', error);
    throw new HTTPException(500, {
      message:
        error instanceof Error ? error.message : 'Failed to fetch projects',
    });
  }
});

// Create project
projects.post('/', async (c) => {
  try {
    const user = requireAuth(c);
    const body = await c.req.json();
    const { name, description } = body;

    if (!name) {
      throw new HTTPException(400, { message: 'Project name is required' });
    }

    // Create project record
    const result = await db
      .insert(schema.projects)
      .values({
        name,
        description: description || null,
        status: 'active',
        createdBy: user.id,
      })
      .returning();

    const project = result[0];

    return c.json({
      success: true,
      project,
      message: 'Project created successfully',
    });
  } catch (error) {
    console.error('Project creation error:', error);
    if (error instanceof HTTPException) {
      throw error;
    }
    throw new HTTPException(500, {
      message:
        error instanceof Error ? error.message : 'Failed to create project',
    });
  }
});

// Get single project
projects.get('/:id', async (c) => {
  try {
    const user = requireAuth(c);
    const id = parseInt(c.req.param('id'));

    if (isNaN(id)) {
      throw new HTTPException(400, { message: 'Invalid project ID' });
    }

    const [project] = await db
      .select()
      .from(schema.projects)
      .where(eq(schema.projects.id, id))
      .limit(1);

    if (!project) {
      throw new HTTPException(404, { message: 'Project not found' });
    }

    // Verify ownership
    if (project.createdBy !== user.id) {
      throw new HTTPException(403, { message: 'Access denied' });
    }

    // Fetch related work items and datasets
    const workItems = await db
      .select()
      .from(schema.workItems)
      .where(eq(schema.workItems.projectId, id));

    const datasets = await db
      .select()
      .from(schema.datasets)
      .where(eq(schema.datasets.projectId, id));

    return c.json({
      success: true,
      project: {
        ...project,
        workItems,
        datasets,
      },
    });
  } catch (error) {
    if (error instanceof HTTPException) {
      throw error;
    }
    console.error('Project fetch error:', error);
    throw new HTTPException(500, {
      message: error instanceof Error ? error.message : 'Failed to fetch project',
    });
  }
});

// Update project
projects.put('/:id', async (c) => {
  try {
    const user = requireAuth(c);
    const id = parseInt(c.req.param('id'));
    const body = await c.req.json();

    if (isNaN(id)) {
      throw new HTTPException(400, { message: 'Invalid project ID' });
    }

    // Check ownership
    const [existingProject] = await db
      .select()
      .from(schema.projects)
      .where(eq(schema.projects.id, id))
      .limit(1);

    if (!existingProject) {
      throw new HTTPException(404, { message: 'Project not found' });
    }

    if (existingProject.createdBy !== user.id) {
      throw new HTTPException(403, { message: 'Access denied' });
    }

    // Update project
    const [updatedProject] = await db
      .update(schema.projects)
      .set({
        name: body.name,
        description: body.description,
        status: body.status,
        updatedAt: new Date(),
      })
      .where(eq(schema.projects.id, id))
      .returning();

    return c.json({
      success: true,
      project: updatedProject,
      message: 'Project updated successfully',
    });
  } catch (error) {
    if (error instanceof HTTPException) {
      throw error;
    }
    console.error('Project update error:', error);
    throw new HTTPException(500, {
      message: error instanceof Error ? error.message : 'Failed to update project',
    });
  }
});

// Delete project
projects.delete('/:id', async (c) => {
  try {
    const user = requireAuth(c);
    const id = parseInt(c.req.param('id'));

    if (isNaN(id)) {
      throw new HTTPException(400, { message: 'Invalid project ID' });
    }

    // Check ownership
    const [existingProject] = await db
      .select()
      .from(schema.projects)
      .where(eq(schema.projects.id, id))
      .limit(1);

    if (!existingProject) {
      throw new HTTPException(404, { message: 'Project not found' });
    }

    if (existingProject.createdBy !== user.id) {
      throw new HTTPException(403, { message: 'Access denied' });
    }

    // Delete project
    await db.delete(schema.projects).where(eq(schema.projects.id, id));

    return c.json({
      success: true,
      message: 'Project deleted successfully',
    });
  } catch (error) {
    if (error instanceof HTTPException) {
      throw error;
    }
    console.error('Project delete error:', error);
    throw new HTTPException(500, {
      message: error instanceof Error ? error.message : 'Failed to delete project',
    });
  }
});

export default projects;
