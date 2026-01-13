/**
 * User Zod schemas for validation
 */
import { z } from 'zod';

export const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  phone: z.string().optional(),
  password: z.string(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});

export const SignUpSchema = z.object({
  email: z.string().email(),
  phone: z.string().optional(),
  password: z.string().min(6),
});

export const SignInSchema = z.object({
  identifier: z.string().min(1),
  password: z.string().min(1),
});

export type User = z.infer<typeof UserSchema>;
export type SignUpDto = z.infer<typeof SignUpSchema>;
export type SignInDto = z.infer<typeof SignInSchema>;
