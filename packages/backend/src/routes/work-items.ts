import { Hono } from 'hono';
import { authMiddleware } from '../middleware/auth.js';

const workItems = new Hono();
workItems.use('*', authMiddleware);

// TODO: Migrate work items routes from server/api/work-items/

export default workItems;
