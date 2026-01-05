import { Hono } from 'hono';
import { authMiddleware } from '../middleware/auth.js';

const predict = new Hono();
predict.use('*', authMiddleware);

// TODO: Migrate predict routes (inline, by-file)

export default predict;
