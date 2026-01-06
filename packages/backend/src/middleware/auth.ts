import { Context, Next } from 'hono';
import jwt from 'jsonwebtoken';
import { db, schema } from '../database/index.js';
import { eq } from 'drizzle-orm';
import {
  UnauthorizedError,
  InternalServerError,
} from '../errors/index.js';

export interface AuthUser {
  id: string;
  email: string;
  phone?: string | null;
}

declare module 'hono' {
  interface ContextVariableMap {
    user: AuthUser;
  }
}

export async function authMiddleware(c: Context, next: Next) {
  const authHeader = c.req.header('authorization');
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    throw new UnauthorizedError('Authentication required');
  }

  const token = authHeader.substring(7); // Remove "Bearer "
  const jwtSecret = process.env.JWT_SECRET;

  if (!jwtSecret) {
    throw new InternalServerError('Server configuration error');
  }

  try {
    const decoded = jwt.verify(token, jwtSecret) as { userId: string };
    const userId = decoded.userId;

    // Fetch user from database
    const [user] = await db
      .select({
        id: schema.users.id,
        email: schema.users.email,
        phone: schema.users.phone,
      })
      .from(schema.users)
      .where(eq(schema.users.id, userId))
      .limit(1);

    if (!user) {
      throw new UnauthorizedError('Invalid token');
    }

    c.set('user', user);
    await next();
  } catch (error) {
    if (error instanceof jwt.JsonWebTokenError) {
      throw new UnauthorizedError('Invalid token');
    }
    throw error;
  }
}

export function requireAuth(c: Context): AuthUser {
  const user = c.get('user');
  if (!user) {
    throw new UnauthorizedError('Authentication required');
  }
  return user;
}
