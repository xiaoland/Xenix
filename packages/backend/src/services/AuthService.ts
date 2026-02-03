/**
 * Auth Service
 * Business logic for authentication and authorization
 */
import bcrypt from "bcrypt";
import { and, eq, or } from "drizzle-orm";
import jwt from "jsonwebtoken";

import type {
  ChangePasswordDto,
  SignInDto,
  SignUpDto,
  UpdateUserDto,
  UserRole,
} from "@xenix/shared";

import { db, schema } from "../database";
import {
  ConflictError,
  ForbiddenError,
  InternalServerError,
  NotFoundError,
  UnauthorizedError,
} from "../errors";

export interface AuthUser {
  id: string;
  email: string;
  phone?: string | null;
  role: UserRole;
  isActive: boolean;
}

export class AuthService {
  /**
   * Sign in a user with credentials
   */
  async signIn(
    credentials: SignInDto & { rememberMe?: boolean },
  ): Promise<{ token: string; user: AuthUser }> {
    const { identifier, password, rememberMe } = credentials;

    // Find user by email or phone
    const [user] = await db
      .select()
      .from(schema.users)
      .where(
        or(
          eq(schema.users.email, identifier),
          eq(schema.users.phone, identifier),
        ),
      )
      .limit(1);

    if (!user) {
      throw new UnauthorizedError("Invalid credentials");
    }

    if (!user.isActive) {
      throw new ForbiddenError("Account is deactivated");
    }

    // Verify password
    const isPasswordValid = await bcrypt.compare(password, user.password);
    if (!isPasswordValid) {
      throw new UnauthorizedError("Invalid credentials");
    }

    // Update last login time
    await db
      .update(schema.users)
      .set({ lastLoginAt: new Date() })
      .where(eq(schema.users.id, user.id));

    // Generate JWT token
    const jwtSecret = process.env.JWT_SECRET;
    if (!jwtSecret) {
      throw new InternalServerError("Server configuration error");
    }

    // Use longer expiration if rememberMe is true (30 days), otherwise 1 day
    const expiresIn = rememberMe ? "30d" : "1d";

    const token = jwt.sign({ userId: user.id }, jwtSecret, {
      expiresIn,
    });

    const authUser: AuthUser = {
      id: user.id,
      email: user.email,
      phone: user.phone,
      role: user.role,
      isActive: user.isActive,
    };

    return { token, user: authUser };
  }

  /**
   * Sign up a new user
   */
  async signUp(data: SignUpDto): Promise<{ token: string; user: AuthUser }> {
    const { email, phone, password } = data;

    // Check if user already exists
    const existingUser = await db
      .select()
      .from(schema.users)
      .where(
        or(eq(schema.users.email, email), eq(schema.users.phone, phone || "")),
      )
      .limit(1);

    if (existingUser.length > 0) {
      throw new ConflictError("User with this email or phone already exists");
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
        role: "user",
        isActive: true,
      })
      .returning();

    // Generate JWT token
    const jwtSecret = process.env.JWT_SECRET;
    if (!jwtSecret) {
      throw new InternalServerError("Server configuration error");
    }

    const token = jwt.sign({ userId: newUser.id }, jwtSecret, {
      expiresIn: "7d",
    });

    const authUser: AuthUser = {
      id: newUser.id,
      email: newUser.email,
      phone: newUser.phone,
      role: newUser.role,
      isActive: newUser.isActive,
    };

    return { token, user: authUser };
  }

  /**
   * Get current user by ID
   */
  async getUserById(userId: string): Promise<AuthUser> {
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
      throw new NotFoundError("User not found");
    }

    return user;
  }

  /**
   * Get all users (admin only)
   */
  async getAllUsers(): Promise<AuthUser[]> {
    const users = await db
      .select({
        id: schema.users.id,
        email: schema.users.email,
        phone: schema.users.phone,
        role: schema.users.role,
        isActive: schema.users.isActive,
      })
      .from(schema.users)
      .orderBy(schema.users.createdAt);

    return users;
  }

  /**
   * Update user (admin only or self)
   */
  async updateUser(userId: string, data: UpdateUserDto): Promise<AuthUser> {
    const updateData: Partial<typeof schema.users.$inferInsert> = {};

    if (data.email !== undefined) updateData.email = data.email;
    if (data.phone !== undefined) updateData.phone = data.phone;
    if (data.role !== undefined) updateData.role = data.role;
    if (data.isActive !== undefined) updateData.isActive = data.isActive;
    updateData.updatedAt = new Date();

    const [updatedUser] = await db
      .update(schema.users)
      .set(updateData)
      .where(eq(schema.users.id, userId))
      .returning({
        id: schema.users.id,
        email: schema.users.email,
        phone: schema.users.phone,
        role: schema.users.role,
        isActive: schema.users.isActive,
      });

    if (!updatedUser) {
      throw new NotFoundError("User not found");
    }

    return updatedUser;
  }

  /**
   * Change user password
   */
  async changePassword(userId: string, data: ChangePasswordDto): Promise<void> {
    const { currentPassword, newPassword } = data;

    // Get user with password
    const [user] = await db
      .select({ password: schema.users.password })
      .from(schema.users)
      .where(eq(schema.users.id, userId))
      .limit(1);

    if (!user) {
      throw new NotFoundError("User not found");
    }

    // Verify current password
    const isPasswordValid = await bcrypt.compare(
      currentPassword,
      user.password,
    );
    if (!isPasswordValid) {
      throw new UnauthorizedError("Current password is incorrect");
    }

    // Hash new password
    const hashedPassword = await bcrypt.hash(newPassword, 10);

    // Update password
    await db
      .update(schema.users)
      .set({
        password: hashedPassword,
        updatedAt: new Date(),
      })
      .where(eq(schema.users.id, userId));
  }

  /**
   * Delete user (admin only)
   */
  async deleteUser(userId: string): Promise<void> {
    const [deletedUser] = await db
      .delete(schema.users)
      .where(eq(schema.users.id, userId))
      .returning({ id: schema.users.id });

    if (!deletedUser) {
      throw new NotFoundError("User not found");
    }
  }

  /**
   * Verify a JWT token and return user ID
   */
  verifyToken(token: string): { userId: string } {
    const jwtSecret = process.env.JWT_SECRET;
    if (!jwtSecret) {
      throw new InternalServerError("Server configuration error");
    }

    try {
      const decoded = jwt.verify(token, jwtSecret) as { userId: string };
      return decoded;
    } catch (error) {
      throw new UnauthorizedError("Invalid or expired token");
    }
  }

  /**
   * Initialize default permissions
   */
  async initializePermissions(): Promise<void> {
    const defaultPermissions = [
      // User management
      {
        name: "users:read",
        description: "View users",
        resource: "users",
        action: "read",
      },
      {
        name: "users:create",
        description: "Create users",
        resource: "users",
        action: "create",
      },
      {
        name: "users:update",
        description: "Update users",
        resource: "users",
        action: "update",
      },
      {
        name: "users:delete",
        description: "Delete users",
        resource: "users",
        action: "delete",
      },
      // Project management
      {
        name: "projects:read",
        description: "View projects",
        resource: "projects",
        action: "read",
      },
      {
        name: "projects:create",
        description: "Create projects",
        resource: "projects",
        action: "create",
      },
      {
        name: "projects:update",
        description: "Update projects",
        resource: "projects",
        action: "update",
      },
      {
        name: "projects:delete",
        description: "Delete projects",
        resource: "projects",
        action: "delete",
      },
      // Dataset management
      {
        name: "datasets:read",
        description: "View datasets",
        resource: "datasets",
        action: "read",
      },
      {
        name: "datasets:create",
        description: "Create datasets",
        resource: "datasets",
        action: "create",
      },
      {
        name: "datasets:update",
        description: "Update datasets",
        resource: "datasets",
        action: "update",
      },
      {
        name: "datasets:delete",
        description: "Delete datasets",
        resource: "datasets",
        action: "delete",
      },
      // Work item management
      {
        name: "work-items:read",
        description: "View work items",
        resource: "work-items",
        action: "read",
      },
      {
        name: "work-items:create",
        description: "Create work items",
        resource: "work-items",
        action: "create",
      },
      {
        name: "work-items:update",
        description: "Update work items",
        resource: "work-items",
        action: "update",
      },
      {
        name: "work-items:delete",
        description: "Delete work items",
        resource: "work-items",
        action: "delete",
      },
      // Task management
      {
        name: "tasks:read",
        description: "View tasks",
        resource: "tasks",
        action: "read",
      },
      {
        name: "tasks:create",
        description: "Create tasks",
        resource: "tasks",
        action: "create",
      },
      {
        name: "tasks:update",
        description: "Update tasks",
        resource: "tasks",
        action: "update",
      },
      {
        name: "tasks:delete",
        description: "Delete tasks",
        resource: "tasks",
        action: "delete",
      },
      // ML Backend management
      {
        name: "ml-backends:read",
        description: "View ML backends",
        resource: "ml-backends",
        action: "read",
      },
      {
        name: "ml-backends:create",
        description: "Create ML backends",
        resource: "ml-backends",
        action: "create",
      },
      {
        name: "ml-backends:update",
        description: "Update ML backends",
        resource: "ml-backends",
        action: "update",
      },
      {
        name: "ml-backends:delete",
        description: "Delete ML backends",
        resource: "ml-backends",
        action: "delete",
      },
    ];

    for (const perm of defaultPermissions) {
      const existing = await db
        .select()
        .from(schema.permissions)
        .where(eq(schema.permissions.name, perm.name))
        .limit(1);

      if (existing.length === 0) {
        await db.insert(schema.permissions).values(perm);
      }
    }

    // Assign all permissions to admin role
    const allPermissions = await db.select().from(schema.permissions);
    for (const perm of allPermissions) {
      const existing = await db
        .select()
        .from(schema.rolePermissions)
        .where(
          and(
            eq(schema.rolePermissions.role, "admin"),
            eq(schema.rolePermissions.permissionId, perm.id),
          ),
        )
        .limit(1);

      if (existing.length === 0) {
        await db.insert(schema.rolePermissions).values({
          role: "admin",
          permissionId: perm.id,
        });
      }
    }

    // Assign basic permissions to user role
    const userPermissions = [
      "projects:read",
      "projects:create",
      "projects:update",
      "datasets:read",
      "datasets:create",
      "datasets:update",
      "work-items:read",
      "work-items:create",
      "work-items:update",
      "tasks:read",
      "tasks:create",
      "ml-backends:read",
    ];

    for (const permName of userPermissions) {
      const [perm] = await db
        .select()
        .from(schema.permissions)
        .where(eq(schema.permissions.name, permName))
        .limit(1);

      if (perm) {
        const existing = await db
          .select()
          .from(schema.rolePermissions)
          .where(
            and(
              eq(schema.rolePermissions.role, "user"),
              eq(schema.rolePermissions.permissionId, perm.id),
            ),
          )
          .limit(1);

        if (existing.length === 0) {
          await db.insert(schema.rolePermissions).values({
            role: "user",
            permissionId: perm.id,
          });
        }
      }
    }
  }

  /**
   * Check if user has permission
   */
  async hasPermission(
    userId: string,
    permissionName: string,
  ): Promise<boolean> {
    // Get user role
    const [user] = await db
      .select({ role: schema.users.role })
      .from(schema.users)
      .where(eq(schema.users.id, userId))
      .limit(1);

    if (!user) return false;

    // Admin has all permissions
    if (user.role === "admin") return true;

    // Check specific permission
    const [permission] = await db
      .select()
      .from(schema.permissions)
      .where(eq(schema.permissions.name, permissionName))
      .limit(1);

    if (!permission) return false;

    const [rolePerm] = await db
      .select()
      .from(schema.rolePermissions)
      .where(
        and(
          eq(schema.rolePermissions.role, user.role),
          eq(schema.rolePermissions.permissionId, permission.id),
        ),
      )
      .limit(1);

    return !!rolePerm;
  }

  /**
   * Get user permissions
   */
  async getUserPermissions(userId: string): Promise<string[]> {
    // Get user role
    const [user] = await db
      .select({ role: schema.users.role })
      .from(schema.users)
      .where(eq(schema.users.id, userId))
      .limit(1);

    if (!user) return [];

    // Admin has all permissions
    if (user.role === "admin") {
      const allPerms = await db
        .select({ name: schema.permissions.name })
        .from(schema.permissions);
      return allPerms.map((p) => p.name);
    }

    // Get role permissions
    const perms = await db
      .select({ name: schema.permissions.name })
      .from(schema.rolePermissions)
      .innerJoin(
        schema.permissions,
        eq(schema.rolePermissions.permissionId, schema.permissions.id),
      )
      .where(eq(schema.rolePermissions.role, user.role));

    return perms.map((p) => p.name);
  }
}
