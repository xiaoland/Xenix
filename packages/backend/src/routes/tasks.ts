import { Hono } from 'hono';
import { authMiddleware } from '../middleware/auth.js';

const tasks = new Hono();
tasks.use('*', authMiddleware);

// TODO: Migrate task routes from server/api/tasks/

export default tasks;
