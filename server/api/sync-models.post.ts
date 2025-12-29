import { syncModelMetadata } from "../utils/syncModels";

/**
 * API endpoint to manually synchronize model metadata
 */
export default defineEventHandler(async (event) => {
  try {
    const result = await syncModelMetadata();
    return result;
  } catch (error: any) {
    throw createError({
      statusCode: 500,
      message: `Failed to sync model metadata: ${error.message}`,
    });
  }
});
