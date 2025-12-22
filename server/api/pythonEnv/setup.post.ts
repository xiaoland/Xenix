import { setupEnvironment } from "../../business/ml";

export default defineEventHandler(async (event) => {
  try {
    const status = await setupEnvironment();

    return {
      success: true,
      message: "Python environment setup initiated",
      status,
    };
  } catch (error) {
    console.error("Error setting up Python environment:", error);
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error ? error.message : "Failed to setup environment",
    });
  }
});
