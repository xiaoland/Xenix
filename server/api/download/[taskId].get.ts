import { db, schema } from "../../database";
import { eq } from "drizzle-orm";
import { readFile } from "fs/promises";
import { resolve } from "path";

export default defineEventHandler(async (event) => {
  const taskId = getRouterParam(event, "taskId");

  if (!taskId) {
    throw createError({
      statusCode: 400,
      message: "Task ID is required",
    });
  }

  try {
    // Get task info
    const [task] = await db
      .select()
      .from(schema.tasks)
      .where(eq(schema.tasks.taskId, taskId))
      .limit(1);

    if (!task) {
      throw createError({
        statusCode: 404,
        message: "Task not found",
      });
    }

    // Only allow downloading completed prediction tasks
    if (task.type !== "prediction") {
      throw createError({
        statusCode: 400,
        message: "Only prediction task results can be downloaded",
      });
    }

    if (task.status !== "completed") {
      throw createError({
        statusCode: 400,
        message: "Task is not completed yet",
      });
    }

    if (!task.outputFile) {
      throw createError({
        statusCode: 404,
        message: "Output file not found",
      });
    }

    // Read the file
    const filePath = resolve(task.outputFile);
    const fileBuffer = await readFile(filePath);
    const fileName = task.outputFile.split(/[\\/]/).pop() || "predictions.xlsx";

    // Set response headers for file download
    setResponseHeaders(event, {
      "Content-Type":
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition": `attachment; filename="${fileName}"`,
      "Content-Length": fileBuffer.length.toString(),
    });

    return fileBuffer;
  } catch (error) {
    console.error("Download error:", error);
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error ? error.message : "Failed to download file",
    });
  }
});
