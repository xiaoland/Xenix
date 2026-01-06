import { Hono } from 'hono';
import { zValidator } from '@hono/zod-validator';
import { db, schema } from '../database/index.js';
import { desc, eq } from 'drizzle-orm';
import { authMiddleware, requireAuth } from '../middleware/auth.js';
import { CreateProjectSchema, UpdateProjectSchema } from '@xenix/shared';
import { NotFoundError, BadRequestError, ForbiddenError } from '../errors/index.js';

const projects = new Hono();

// Apply auth middleware to all routes
projects.use('*', authMiddleware);

// Get all projects
projects.get('/', async (c) => {
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
});

// Create project
projects.post(
  '/',
  zValidator('json', CreateProjectSchema),
  async (c) => {
    const user = requireAuth(c);
    const { name, description } = c.req.valid('json');

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
  }
);

// Get single project
projects.get('/:id', async (c) => {
  const user = requireAuth(c);
  const id = parseInt(c.req.param('id'));

  if (isNaN(id)) {
    throw new BadRequestError('Invalid project ID');
  }

  const [project] = await db
    .select()
    .from(schema.projects)
    .where(eq(schema.projects.id, id))
    .limit(1);

  if (!project) {
    throw new NotFoundError('Project');
  }

  // Verify ownership
  if (project.createdBy !== user.id) {
    throw new ForbiddenError('Access denied to this project');
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
});

// Update project
projects.put(
  '/:id',
  zValidator('json', UpdateProjectSchema),
  async (c) => {
    const user = requireAuth(c);
    const id = parseInt(c.req.param('id'));
    const updates = c.req.valid('json');

    if (isNaN(id)) {
      throw new BadRequestError('Invalid project ID');
    }

    // Check ownership
    const [existingProject] = await db
      .select()
      .from(schema.projects)
      .where(eq(schema.projects.id, id))
      .limit(1);

    if (!existingProject) {
      throw new NotFoundError('Project');
    }

    if (existingProject.createdBy !== user.id) {
      throw new ForbiddenError('Access denied to this project');
    }

    // Update project
    const [updatedProject] = await db
      .update(schema.projects)
      .set({
        ...updates,
        updatedAt: new Date(),
      })
      .where(eq(schema.projects.id, id))
      .returning();

    return c.json({
      success: true,
      project: updatedProject,
      message: 'Project updated successfully',
    });
  }
);

// Delete project
projects.delete('/:id', async (c) => {
  const user = requireAuth(c);
  const id = parseInt(c.req.param('id'));

  if (isNaN(id)) {
    throw new BadRequestError('Invalid project ID');
  }

  // Check ownership
  const [existingProject] = await db
    .select()
    .from(schema.projects)
    .where(eq(schema.projects.id, id))
    .limit(1);

  if (!existingProject) {
    throw new NotFoundError('Project');
  }

  if (existingProject.createdBy !== user.id) {
    throw new ForbiddenError('Access denied to this project');
  }

  // Delete project
  await db.delete(schema.projects).where(eq(schema.projects.id, id));

  return c.json({
    success: true,
    message: 'Project deleted successfully',
  });
});

export default projects;

    });
  }
});

export default projects;
