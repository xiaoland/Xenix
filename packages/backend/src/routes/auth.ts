import bcrypt from 'bcrypt';
import { eq, or } from 'drizzle-orm';
import jwt from 'jsonwebtoken';

import { zValidator } from '@hono/zod-validator';
import { Hono } from 'hono';

import { SignInSchema, SignUpSchema } from '@xenix/shared';

import { db, schema } from '../database/index.js';
import {
  ConflictError,
  InternalServerError,
  UnauthorizedError,
} from '../errors/index.js';

const auth = new Hono()

  // Sign in - returns token directly (HTTP semantics)
  .post('/signin', zValidator('json', SignInSchema), async (c) => {
    const { identifier, password } = c.req.valid('json');

    // Find user by email or phone
    const [user] = await db
      .select()
      .from(schema.users)
      .where(
        or(
          eq(schema.users.email, identifier),
          eq(schema.users.phone, identifier)
        )
      )
      .limit(1);

    if (!user) {
      throw new UnauthorizedError('Invalid credentials');
    }

    // Verify password
    const isPasswordValid = await bcrypt.compare(password, user.password);
    if (!isPasswordValid) {
      throw new UnauthorizedError('Invalid credentials');
    }

    // Generate JWT token
    const jwtSecret = process.env.JWT_SECRET;
    if (!jwtSecret) {
      throw new InternalServerError('Server configuration error');
    }

    const token = jwt.sign({ userId: user.id }, jwtSecret, {
      expiresIn: '7d',
    });

    // Return token directly (no envelope)
    return c.json({ token });
  })

  // Sign up - returns token directly (HTTP semantics)
  .post('/signup', zValidator('json', SignUpSchema), async (c) => {
    const { email, phone, password } = c.req.valid('json');

    // Check if user already exists
    const existingUser = await db
      .select()
      .from(schema.users)
      .where(
        or(eq(schema.users.email, email), eq(schema.users.phone, phone || ''))
      )
      .limit(1);

    if (existingUser.length > 0) {
      throw new ConflictError('User with this email or phone already exists');
    }

    // Hash password
    const hashedPassword = await bcrypt.hash(password, 10);

    // Create user
    const [newUser] = await db
      .insert(schema.users)
      .values({
        email,
        phone: phone || null,
        password: hashedPassword,
      })
      .returning();

    // Generate JWT token
    const jwtSecret = process.env.JWT_SECRET;
    if (!jwtSecret) {
      throw new InternalServerError('Server configuration error');
    }

    const token = jwt.sign({ userId: newUser.id }, jwtSecret, {
      expiresIn: '7d',
    });

    // Return token directly (no envelope)
    return c.json({ token });
  });

export default auth;
