import { Hono } from 'hono';
import { authMiddleware } from '../middleware/auth.js';

const models = new Hono();
models.use('*', authMiddleware);

// TODO: Migrate model routes from server/api/models/

export default models;
