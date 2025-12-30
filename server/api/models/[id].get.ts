/**
 * API endpoint to retrieve a single model metadata by name
 */
import { db } from "../../database";
import { modelMetadata } from "../../database/schema";
import { eq } from "drizzle-orm";

export default defineEventHandler(async (event) => {
  try {
    const id = getRouterParam(event, "id");

    if (!id) {
      throw createError({
        statusCode: 400,
        statusMessage: "Model name is required",
      });
    }

    const model = await db
      .select()
      .from(modelMetadata)
      .where(eq(modelMetadata.name, id))
      .limit(1);

    if (model.length === 0) {
      throw createError({
        statusCode: 404,
        statusMessage: "Model not found",
      });
    }

    return {
      success: true,
      model: model[0],
    };
  } catch (error: any) {
    console.error("Failed to fetch model metadata:", error);
    throw createError({
      statusCode: error.statusCode || 500,
      statusMessage: error.statusMessage || "Failed to fetch model metadata",
    });
  }
});
