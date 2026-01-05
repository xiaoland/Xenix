import { db, schema } from "../../database";
import bcrypt from "bcrypt";
import { eq } from "drizzle-orm";

export default defineEventHandler(async (event) => {
  try {
    const body = await readBody(event);
    const { email, phone, password } = body;

    // Validation
    if (!email || typeof email !== "string" || !email.includes("@")) {
      throw createError({
        statusCode: 400,
        statusMessage: "Valid email is required",
      });
    }

    if (!password || typeof password !== "string" || password.length < 8) {
      throw createError({
        statusCode: 400,
        statusMessage: "Password must be at least 8 characters long",
      });
    }

    // Check if at least email or phone is provided (email is required, so this is always true if email is provided)
    if (!email && !phone) {
      throw createError({
        statusCode: 400,
        statusMessage: "At least email or phone must be provided",
      });
    }

    // Check if user already exists
    const existingUser = await db
      .select()
      .from(schema.users)
      .where(eq(schema.users.email, email))
      .limit(1);

    if (existingUser.length > 0) {
      throw createError({
        statusCode: 409,
        statusMessage: "User with this email already exists",
      });
    }

    // Hash the password
    const hashedPassword = await bcrypt.hash(password, 12);

    // Create the user
    const [newUser] = await db
      .insert(schema.users)
      .values({
        email,
        phone: phone || null,
        password: hashedPassword,
      })
      .returning({
        id: schema.users.id,
        email: schema.users.email,
        phone: schema.users.phone,
        createdAt: schema.users.createdAt,
      });

    // Return success response
    return {
      success: true,
      message: "User created successfully",
      user: newUser,
    };
  } catch (error: any) {
    // If it's already a H3 error, re-throw it
    if (error.statusCode) {
      throw error;
    }

    // Database or other errors
    console.error("Signup error:", error);
    throw createError({
      statusCode: 500,
      statusMessage: "Internal server error",
    });
  }
});
