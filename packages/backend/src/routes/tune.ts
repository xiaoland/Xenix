import { Hono } from 'hono';
import { authMiddleware } from '../middleware/auth.js';

const tune = new Hono();
tune.use('*', authMiddleware);

// TODO: Migrate tune routes (auto-tune, manual-tune)

export default tune;
