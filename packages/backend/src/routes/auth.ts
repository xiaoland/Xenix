import { Hono } from 'hono';
import { HTTPException } from 'hono/http-exception';
import bcrypt from 'bcrypt';
import jwt from 'jsonwebtoken';
import { db, schema } from '../database/index.js';
import { eq, or } from 'drizzle-orm';

const auth = new Hono();

// Sign in
auth.post('/signin', async (c) => {
  try {
    const body = await c.req.json();
    const { identifier, password } = body;

    // Validation
    if (!identifier || typeof identifier !== 'string') {
      throw new HTTPException(400, {
        message: 'Identifier (email or phone) is required',
      });
    }

    if (!password || typeof password !== 'string') {
      throw new HTTPException(400, { message: 'Password is required' });
    }

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
      throw new HTTPException(401, { message: 'Invalid credentials' });
    }

    // Verify password
    const isPasswordValid = await bcrypt.compare(password, user.password);
    if (!isPasswordValid) {
      throw new HTTPException(401, { message: 'Invalid credentials' });
    }

    // Generate JWT token
    const jwtSecret = process.env.JWT_SECRET;
    if (!jwtSecret) {
      throw new HTTPException(500, { message: 'Server configuration error' });
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
  } catch (error: any) {
    if (error instanceof HTTPException) {
      throw error;
    }
    console.error('Signin error:', error);
    throw new HTTPException(500, { message: 'Internal server error' });
  }
});

// Sign up
auth.post('/signup', async (c) => {
  try {
    const body = await c.req.json();
    const { email, phone, password } = body;

    // Validation
    if (!email || typeof email !== 'string') {
      throw new HTTPException(400, { message: 'Email is required' });
    }

    if (!password || typeof password !== 'string') {
      throw new HTTPException(400, { message: 'Password is required' });
    }

    // Check if user already exists
    const existingUser = await db
      .select()
      .from(schema.users)
      .where(
        or(eq(schema.users.email, email), eq(schema.users.phone, phone || ''))
      )
      .limit(1);

    if (existingUser.length > 0) {
      throw new HTTPException(409, {
        message: 'User with this email or phone already exists',
      });
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
      throw new HTTPException(500, { message: 'Server configuration error' });
    }

    const token = jwt.sign({ userId: newUser.id }, jwtSecret, {
      expiresIn: '7d',
    });

    return c.json({
      success: true,
      message: 'Signup successful',
      token,
    });
  } catch (error: any) {
    if (error instanceof HTTPException) {
      throw error;
    }
    console.error('Signup error:', error);
    throw new HTTPException(500, { message: 'Internal server error' });
  }
});

export default auth;
