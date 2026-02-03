/**
 * Auth Types
 *
 * Feature-specific type definitions for authentication
 */

/**
 * User entity
 */
export interface User {
  id: string;
  email: string;
  phone?: string;
  createdAt: string;
  updatedAt: string;
}

/**
 * Auth state
 */
export interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
}

/**
 * Login form values
 */
export interface LoginFormValues {
  identifier: string;
  password: string;
  remember?: boolean;
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
