import { zValidator } from '@hono/zod-validator';
import { Hono } from 'hono';

import {
  CreateWorkItemSchema,
  UpdateWorkItemSchema,
  WorkItemIdParamSchema,
} from '@xenix/shared';

import { authMiddleware, requireAuth } from '../middleware/auth.js';
import { WorkItemService } from '../services/index.js';

const workItems = new Hono();
const workItemService = new WorkItemService();

workItems
  .use('*', authMiddleware)

  // Get all work items
  .get('/', async (c) => {
    const user = requireAuth(c);
    const projectIdQuery = c.req.query('projectId');
    const projectId = projectIdQuery ? Number(projectIdQuery) : undefined;

    const items = await workItemService.getWorkItemsByUser(user.id, projectId);
    return c.json(items);
  })

  // Create work item
  .post('/', zValidator('json', CreateWorkItemSchema), async (c) => {
    const user = requireAuth(c);
    const data = c.req.valid('json');

    const workItem = await workItemService.createWorkItem(user.id, data);
    return c.json(workItem, 201);
  })

  // Get single work item
  .get('/:id', zValidator('param', WorkItemIdParamSchema), async (c) => {
    const user = requireAuth(c);
    const { id: idStr } = c.req.valid('param');
    const id = parseInt(idStr);

    const workItem = await workItemService.getWorkItemById(id, user.id);
    return c.json(workItem);
  })

  // Update work item
  .put(
    '/:id',
    zValidator('param', WorkItemIdParamSchema),
    zValidator('json', UpdateWorkItemSchema),
    async (c) => {
      const user = requireAuth(c);
      const { id: idStr } = c.req.valid('param');
      const id = parseInt(idStr);
      const data = c.req.valid('json');

      const updatedWorkItem = await workItemService.updateWorkItem(
        id,
        user.id,
        data
      );
      return c.json(updatedWorkItem);
    }
  )

  // Delete work item
  .delete('/:id', zValidator('param', WorkItemIdParamSchema), async (c) => {
    const user = requireAuth(c);
    const { id: idStr } = c.req.valid('param');
    const id = parseInt(idStr);

    await workItemService.deleteWorkItem(id, user.id);
    return c.json({ message: 'Work item deleted successfully' });
  });

export default workItems;
