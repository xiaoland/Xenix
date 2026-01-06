import { Hono } from "hono";
import { HTTPException } from "hono/http-exception";
import { db, schema } from "../database/index.js";
import { eq } from "drizzle-orm";
import { authMiddleware } from "../middleware/auth.js";
import { readFile } from "fs/promises";
import { resolve } from "path";

const download = new Hono()
  .use("*", authMiddleware)

  // Download prediction result file
  .get("/:id", async (c) => {
    const id = c.req.param("id");

    if (!id) {
      throw new HTTPException(400, { message: "Task ID is required" });
    }

    try {
      const taskId = parseInt(id);

      // Get task info
      const [task] = await db
        .select()
        .from(schema.tasks)
        .where(eq(schema.tasks.id, taskId))
        .limit(1);

      if (!task) {
        throw new HTTPException(404, { message: "Task not found" });
      }

      // Only allow downloading completed prediction tasks
      if (task.type !== "predict") {
        throw new HTTPException(400, {
          message: "Only prediction task results can be downloaded",
        });
      }

      if (task.status !== "completed") {
        throw new HTTPException(400, { message: "Task is not completed yet" });
      }

      const result: any = task.result || {};
      const outputFile =
        result.outputFile || (task.parameter as any)?.outputFile;

      if (!outputFile) {
        throw new HTTPException(404, { message: "Output file not found" });
      }

      // Read the file
      const filePath = resolve(outputFile);
      const fileBuffer = await readFile(filePath);
      const fileName = outputFile.split(/[\\/]/).pop() || "predictions.xlsx";

      // Set response headers for file download
      c.header(
        "Content-Type",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      );
      c.header("Content-Disposition", `attachment; filename="${fileName}"`);
      c.header("Content-Length", fileBuffer.length.toString());

      return c.body(fileBuffer);
    } catch (error) {
      console.error("Download error:", error);
      if (error instanceof HTTPException) {
        throw error;
      }
      throw new HTTPException(500, {
        message:
          error instanceof Error ? error.message : "Failed to download file",
      });
    }
  });

export default download;
