import { reinstallEnvironment } from "../../business/ml";

export default defineEventHandler(async (event) => {
  try {
    const status = await reinstallEnvironment();

    return {
      success: true,
      message: "Python environment reinstalled",
      status,
    };
  } catch (error) {
    console.error("Error reinstalling Python environment:", error);
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error
          ? error.message
          : "Failed to reinstall environment",
    });
  }
});
