import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthService } from "../../services/AuthService";
import { ConflictError, UnauthorizedError } from "../../errors";

// Mock dependencies
vi.mock("../../database", () => ({
  db: {
    select: vi.fn(),
    insert: vi.fn(),
  },
  schema: {
    users: {
      email: "email",
      phone: "phone",
      password: "password",
    },
  },
}));

vi.mock("bcrypt", () => ({
  default: {
    compare: vi.fn(),
    hash: vi.fn(),
  },
}));

vi.mock("jsonwebtoken", () => ({
  default: {
    sign: vi.fn(),
    verify: vi.fn(),
  },
}));

describe("AuthService", () => {
  let authService: AuthService;

  beforeEach(() => {
    authService = new AuthService();
    vi.clearAllMocks();
    process.env.JWT_SECRET = "test-secret";
  });

  describe("signIn", () => {
    it("should throw UnauthorizedError when user not found", async () => {
      const { db } = await import("../../database");
      const dbMock = db as any;

      dbMock.select.mockReturnValue({
        from: vi.fn().mockReturnValue({
          where: vi.fn().mockReturnValue({
            limit: vi.fn().mockResolvedValue([]),
          }),
        }),
      });

      await expect(
        authService.signIn({
          identifier: "nonexistent@example.com",
          password: "password123",
          rememberMe: false,
        }),
      ).rejects.toThrow(UnauthorizedError);
    });
  });

  describe("signUp", () => {
    it("should throw ConflictError when user already exists", async () => {
      const { db } = await import("../../database");
      const dbMock = db as any;

      dbMock.select.mockReturnValue({
        from: vi.fn().mockReturnValue({
          where: vi.fn().mockReturnValue({
            limit: vi
              .fn()
              .mockResolvedValue([
                { id: "existing-user", email: "existing@example.com" },
              ]),
          }),
        }),
      });

      await expect(
        authService.signUp({
          email: "existing@example.com",
          password: "password123",
        }),
      ).rejects.toThrow(ConflictError);
    });
  });

  describe("verifyToken", () => {
    it("should throw UnauthorizedError for invalid token", () => {
      const jwt = require("jsonwebtoken");
      jwt.default.verify = vi.fn().mockImplementation(() => {
        throw new Error("Invalid token");
      });

      expect(() => authService.verifyToken("invalid-token")).toThrow(
        UnauthorizedError,
      );
    });
  });
});
