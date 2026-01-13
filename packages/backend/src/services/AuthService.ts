/**
 * Auth Service
 * Business logic for authentication and authorization
 */
import bcrypt from 'bcrypt';
import { eq, or } from 'drizzle-orm';
import jwt from 'jsonwebtoken';

import type { SignInDto, SignUpDto } from '@xenix/shared';

import { db, schema } from '../database/index.js';
import {
  ConflictError,
  InternalServerError,
  UnauthorizedError,
} from '../errors/index.js';

export class AuthService {
  /**
   * Sign in a user with credentials
   */
  async signIn(credentials: SignInDto): Promise<{ token: string }> {
    const { identifier, password } = credentials;

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

    return { token };
  }

  /**
   * Sign up a new user
   */
  async signUp(data: SignUpDto): Promise<{ token: string }> {
    const { email, phone, password } = data;

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

    return { token };
  }

  /**
   * Verify a JWT token and return user ID
   */
  verifyToken(token: string): { userId: string } {
    const jwtSecret = process.env.JWT_SECRET;
    if (!jwtSecret) {
      throw new InternalServerError('Server configuration error');
    }

    try {
      const decoded = jwt.verify(token, jwtSecret) as { userId: string };
      return decoded;
    } catch (error) {
      throw new UnauthorizedError('Invalid or expired token');
    }
  }
}
