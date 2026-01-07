import { zValidator } from '@hono/zod-validator';
import { Hono } from 'hono';

import {
  CreateProjectSchema,
  ProjectIdParamSchema,
  UpdateProjectSchema,
} from '@xenix/shared';

import { authMiddleware, requireAuth } from '../middleware/auth.js';
import { ProjectService } from '../services/index.js';

const projects = new Hono();
const projectService = new ProjectService();

projects
  .use('*', authMiddleware)

  // Get all projects - returns array directly (HTTP semantics)
  .get('/', async (c) => {
    const user = requireAuth(c);
    const projectsList = await projectService.getAllProjects(user.id);
    return c.json(projectsList);
  })

  // Create project - returns created project directly (HTTP semantics)
  .post('/', zValidator('json', CreateProjectSchema), async (c) => {
    const user = requireAuth(c);
    const data = c.req.valid('json');
    const project = await projectService.createProject(user.id, data);
    return c.json(project, 201);
  })

  // Get single project - returns project directly (HTTP semantics)
  .get('/:id', zValidator('param', ProjectIdParamSchema), async (c) => {
    const user = requireAuth(c);
    const { id: idStr } = c.req.valid('param');
    const id = parseInt(idStr);
    const project = await projectService.getProjectById(id, user.id);
    return c.json(project);
  })

  // Update project - returns updated project directly (HTTP semantics)
  .put(
    '/:id',
    zValidator('param', ProjectIdParamSchema),
    zValidator('json', UpdateProjectSchema),
    async (c) => {
      const user = requireAuth(c);
      const { id: idStr } = c.req.valid('param');
      const id = parseInt(idStr);
      const data = c.req.valid('json');
      const updatedProject = await projectService.updateProject(
        id,
        user.id,
        data
      );
      return c.json(updatedProject);
    }
  )

  // Delete project - returns success message (HTTP semantics)
  .delete('/:id', zValidator('param', ProjectIdParamSchema), async (c) => {
    const user = requireAuth(c);
    const { id: idStr } = c.req.valid('param');
    const id = parseInt(idStr);
    await projectService.deleteProject(id, user.id);
    return c.json({ message: 'Project deleted successfully' });
  });

export default projects;
