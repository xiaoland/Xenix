import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";

import { SignInSchema, SignUpSchema } from "@xenix/shared";

import { AuthService } from "../services";

const authService = new AuthService();

const auth = new Hono()
  // Sign in - returns token directly (HTTP semantics)
  .post("/signin", zValidator("json", SignInSchema), async (c) => {
    const credentials = c.req.valid("json");
    const result = await authService.signIn(credentials);
    return c.json(result);
  })

  // Sign up - returns token directly (HTTP semantics)
  .post("/signup", zValidator("json", SignUpSchema), async (c) => {
    const data = c.req.valid("json");
    const result = await authService.signUp(data);
    return c.json(result);
  });

export default auth;
