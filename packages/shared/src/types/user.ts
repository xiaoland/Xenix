/**
 * User-related type definitions
 */

export interface User {
  id: string; // UUID
  email: string;
  phone?: string;
  password: string; // Hashed password
  createdAt: string;
  updatedAt: string;
}
