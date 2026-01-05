import { db, schema } from "../../database";
import bcrypt from "bcrypt";
import jwt from "jsonwebtoken";
import { eq, or } from "drizzle-orm";

export default defineEventHandler(async (event) => {
  try {
    const body = await readBody(event);
    const { identifier, password } = body;

    // Validation
    if (!identifier || typeof identifier !== "string") {
      throw createError({
        statusCode: 400,
        statusMessage: "Identifier (email or phone) is required",
      });
    }

    if (!password || typeof password !== "string") {
      throw createError({
        statusCode: 400,
        statusMessage: "Password is required",
      });
    }

    // Find user by email or phone
    const [user] = await db
      .select()
      .from(schema.users)
      .where(
        or(
          eq(schema.users.email, identifier),
          eq(schema.users.phone, identifier)
        )
      )
      .limit(1);

    if (!user) {
      throw createError({
        statusCode: 401,
        statusMessage: "Invalid credentials",
      });
    }

    // Verify password
    const isPasswordValid = await bcrypt.compare(password, user.password);
    if (!isPasswordValid) {
      throw createError({
        statusCode: 401,
        statusMessage: "Invalid credentials",
      });
    }

    // Generate JWT token
    const jwtSecret = process.env.JWT_SECRET;
    if (!jwtSecret) {
      throw createError({
        statusCode: 500,
        statusMessage: "Server configuration error",
      });
    }

    const token = jwt.sign({ userId: user.id }, jwtSecret, { expiresIn: "7d" });

    // Return success response
    return {
      success: true,
      message: "Signin successful",
      token,
    };
  } catch (error: any) {
    // If it's already a H3 error, re-throw it
    if (error.statusCode) {
      throw error;
    }

    // Database or other errors
    console.error("Signin error:", error);
    throw createError({
      statusCode: 500,
      statusMessage: "Internal server error",
    });
  }
});
