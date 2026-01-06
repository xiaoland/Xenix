import { Hono } from 'hono';
import { zValidator } from '@hono/zod-validator';
import bcrypt from 'bcrypt';
import jwt from 'jsonwebtoken';
import { db, schema } from '../database/index.js';
import { eq, or } from 'drizzle-orm';
import { SignInSchema, SignUpSchema } from '@xenix/shared';
import {
  UnauthorizedError,
  ConflictError,
  InternalServerError,
} from '../errors/index.js';

const auth = new Hono();

// Sign in
auth.post('/signin', zValidator('json', SignInSchema), async (c) => {
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

  // Return success response
  return c.json({
    success: true,
    message: 'Signin successful',
    token,
  });
});

// Sign up
auth.post('/signup', zValidator('json', SignUpSchema), async (c) => {
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

  return c.json({
    success: true,
    message: 'Signup successful',
    token,
  });
});

export default auth;
