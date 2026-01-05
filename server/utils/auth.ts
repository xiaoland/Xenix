import jwt from "jsonwebtoken";
import { db, schema } from "../database";
import { eq } from "drizzle-orm";

export interface AuthUser {
  id: string;
  email: string;
  phone?: string;
}

export async function getCurrentUser(event: any): Promise<AuthUser | null> {
  try {
    const authHeader = getHeader(event, "authorization");
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      return null;
    }

    const token = authHeader.substring(7); // Remove "Bearer "
    const jwtSecret = process.env.JWT_SECRET;

    if (!jwtSecret) {
      throw new Error("JWT_SECRET not configured");
    }

    const decoded = jwt.verify(token, jwtSecret) as { userId: string };
    const userId = decoded.userId;

    // Fetch user from database
    const [user] = await db
      .select({
        id: schema.users.id,
        email: schema.users.email,
        phone: schema.users.phone,
      })
      .from(schema.users)
      .where(eq(schema.users.id, userId))
      .limit(1);

    return user || null;
  } catch (error) {
    console.error("Auth error:", error);
    return null;
  }
}

export function requireAuth(user: AuthUser | null): AuthUser {
  if (!user) {
    throw createError({
      statusCode: 401,
      statusMessage: "Authentication required",
    });
  }
  return user;
}
