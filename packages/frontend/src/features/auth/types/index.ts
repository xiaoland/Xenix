/**
 * Auth Types
 *
 * Feature-specific type definitions for authentication
 */
import type { UserRole } from "@xenix/shared";

/**
 * User entity
 */
export interface User {
  id: string;
  email: string;
  phone?: string;
  role: UserRole;
  isActive: boolean;
  lastLoginAt?: string;
  createdAt: string;
  updatedAt: string;
}

/**
 * Auth state
 */
export interface AuthState {
  token: string | null;
  user: User | null;
  permissions: string[];
  isAuthenticated: boolean;
}

/**
 * Login form values
 */
export interface LoginFormValues {
  identifier: string;
  password: string;
  rememberMe?: boolean;
}

/**
 * Signup form values
 */
export interface SignupFormValues {
  email: string;
  password: string;
  confirmPassword: string;
  phone?: string;
  agreeToTerms: boolean;
}

/**
 * Change password form values
 */
export interface ChangePasswordFormValues {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

/**
 * Update user form values
 */
export interface UpdateUserFormValues {
  email?: string;
  phone?: string;
  role?: UserRole;
  isActive?: boolean;
}
