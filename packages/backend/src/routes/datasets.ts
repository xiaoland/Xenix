import { Hono } from 'hono';
import { authMiddleware } from '../middleware/auth.js';

const datasets = new Hono();
datasets.use('*', authMiddleware);

// TODO: Migrate dataset routes from server/api/data/

export default datasets;
