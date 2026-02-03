import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";

import {
  ChangePasswordSchema,
  SignInSchema,
  SignUpSchema,
  UpdateUserSchema,
} from "@xenix/shared";

import { authMiddleware, requireAdmin } from "../middleware/auth";
import { AuthService } from "../services";

const authService = new AuthService();

const auth = new Hono()
  // Sign in - returns token and user info
  .post("/signin", zValidator("json", SignInSchema), async (c) => {
    const credentials = c.req.valid("json");
    const result = await authService.signIn(credentials);
    return c.json(result);
  })

  // Sign up - returns token and user info
  .post("/signup", zValidator("json", SignUpSchema), async (c) => {
    const data = c.req.valid("json");
    const result = await authService.signUp(data);
    return c.json(result);
  })

  // Get current user info
  .get("/me", authMiddleware, async (c) => {
    const user = c.get("user");
    const userInfo = await authService.getUserById(user.id);
    return c.json(userInfo);
  })

  // Update current user
  .patch(
    "/me",
    authMiddleware,
    zValidator("json", UpdateUserSchema),
    async (c) => {
      const user = c.get("user");
      const data = c.req.valid("json");
      const updatedUser = await authService.updateUser(user.id, data);
      return c.json(updatedUser);
    },
  )

  // Change password
  .post(
    "/change-password",
    authMiddleware,
    zValidator("json", ChangePasswordSchema),
    async (c) => {
      const user = c.get("user");
      const data = c.req.valid("json");
      await authService.changePassword(user.id, data);
      return c.json({ message: "Password changed successfully" });
    },
  )

  // Get all users (admin only)
  .get("/users", authMiddleware, requireAdmin, async (c) => {
    const users = await authService.getAllUsers();
    return c.json(users);
  })

  // Get user by ID (admin only)
  .get("/users/:id", authMiddleware, requireAdmin, async (c) => {
    const id = c.req.param("id");
    const user = await authService.getUserById(id);
    return c.json(user);
  })

  // Update user (admin only)
  .patch(
    "/users/:id",
    authMiddleware,
    requireAdmin,
    zValidator("json", UpdateUserSchema),
    async (c) => {
      const id = c.req.param("id");
      const data = c.req.valid("json");
      const updatedUser = await authService.updateUser(id, data);
      return c.json(updatedUser);
    },
  )

  // Delete user (admin only)
  .delete("/users/:id", authMiddleware, requireAdmin, async (c) => {
    const id = c.req.param("id");
    await authService.deleteUser(id);
    return c.json({ message: "User deleted successfully" });
  })

  // Get current user permissions
  .get("/permissions", authMiddleware, async (c) => {
    const user = c.get("user");
    const permissions = await authService.getUserPermissions(user.id);
    return c.json({ permissions });
  })

  // Initialize permissions (admin only, for setup)
  .post("/init-permissions", authMiddleware, requireAdmin, async (c) => {
    await authService.initializePermissions();
    return c.json({ message: "Permissions initialized successfully" });
  });

export default auth;
