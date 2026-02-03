import { eq } from "drizzle-orm";
import jwt from "jsonwebtoken";

import { Context, Next } from "hono";

import { db, schema } from "../database";
import {
  ForbiddenError,
  InternalServerError,
  UnauthorizedError,
} from "../errors";
import type { UserRole } from "@xenix/shared";

export interface AuthUser {
  id: string;
  email: string;
  phone?: string | null;
  role: UserRole;
  isActive: boolean;
}

declare module "hono" {
  interface ContextVariableMap {
    user: AuthUser;
  }
}

export async function authMiddleware(c: Context, next: Next) {
  const authHeader = c.req.header("authorization");
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    throw new UnauthorizedError("Authentication required");
  }

  const token = authHeader.substring(7); // Remove "Bearer "
  const jwtSecret = process.env.JWT_SECRET;

  if (!jwtSecret) {
    throw new InternalServerError("Server configuration error");
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
        role: schema.users.role,
        isActive: schema.users.isActive,
      })
      .from(schema.users)
      .where(eq(schema.users.id, userId))
      .limit(1);

    if (!user) {
      throw new UnauthorizedError("Invalid token");
    }

    if (!user.isActive) {
      throw new ForbiddenError("Account is deactivated");
    }

    c.set("user", user);
    await next();
  } catch (error) {
    if (error instanceof jwt.JsonWebTokenError) {
      throw new UnauthorizedError("Invalid token");
    }
    throw error;
  }
}

export function requireAuth(c: Context): AuthUser {
  const user = c.get("user");
  if (!user) {
    throw new UnauthorizedError("Authentication required");
  }
  return user;
}

/**
 * Middleware to require admin role
 */
export async function requireAdmin(c: Context, next: Next) {
  const user = requireAuth(c);

  if (user.role !== "admin") {
    throw new ForbiddenError("Admin access required");
  }

  await next();
}

/**
 * Middleware factory to check specific permission
 */
export function requirePermission(permission: string) {
  return async (c: Context, next: Next) => {
    const user = requireAuth(c);

    // Admin has all permissions
    if (user.role === "admin") {
      await next();
      return;
    }

    // Check specific permission
    const [perm] = await db
      .select()
      .from(schema.permissions)
      .where(eq(schema.permissions.name, permission))
      .limit(1);

    if (!perm) {
      throw new ForbiddenError(`Permission '${permission}' not found`);
    }

    const [rolePerm] = await db
      .select()
      .from(schema.rolePermissions)
      .where(
        eq(schema.rolePermissions.role, user.role) &&
          eq(schema.rolePermissions.permissionId, perm.id),
      )
      .limit(1);

    if (!rolePerm) {
      throw new ForbiddenError(`Permission '${permission}' required`);
    }

    await next();
  };
}
