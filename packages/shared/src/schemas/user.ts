/**
 * User Zod schemas for validation
 */
import { z } from "zod";

// User role enum
export const UserRoleEnum = z.enum(["admin", "user"]);

export const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  phone: z.string().optional(),
  role: UserRoleEnum,
  isActive: z.boolean(),
  lastLoginAt: z.string().datetime().optional(),
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
  rememberMe: z.boolean().optional().default(false),
});

export const UpdateUserSchema = z.object({
  email: z.string().email().optional(),
  phone: z.string().optional(),
  role: UserRoleEnum.optional(),
  isActive: z.boolean().optional(),
});

export const ChangePasswordSchema = z.object({
  currentPassword: z.string().min(1),
  newPassword: z.string().min(6),
});

export const PermissionSchema = z.object({
  id: z.number(),
  name: z.string(),
  description: z.string().optional(),
  resource: z.string(),
  action: z.string(),
  createdAt: z.string().datetime(),
});

export const RolePermissionSchema = z.object({
  id: z.number(),
  role: UserRoleEnum,
  permissionId: z.number(),
  createdAt: z.string().datetime(),
});

export type User = z.infer<typeof UserSchema>;
export type UserRole = z.infer<typeof UserRoleEnum>;
export type SignUpDto = z.infer<typeof SignUpSchema>;
export type SignInDto = z.infer<typeof SignInSchema>;
export type UpdateUserDto = z.infer<typeof UpdateUserSchema>;
export type ChangePasswordDto = z.infer<typeof ChangePasswordSchema>;
export type Permission = z.infer<typeof PermissionSchema>;
export type RolePermission = z.infer<typeof RolePermissionSchema>;
