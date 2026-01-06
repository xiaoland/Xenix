import { Hono } from "hono";
import { db, schema } from "../database/index.js";
import { eq } from "drizzle-orm";
import { authMiddleware } from "../middleware/auth.js";
import { readFile } from "fs/promises";
import { resolve } from "path";
import {
  NotFoundError,
  BadRequestError,
} from "../errors/index.js";
import logger from "../utils/logger/index.js";

const download = new Hono()
  .use("*", authMiddleware)

  // Download prediction result file
  .get("/:id", async (c) => {
    const id = c.req.param("id");

    if (!id) {
      throw new BadRequestError("Task ID is required");
    }

    const taskId = parseInt(id);

    // Get task info
    const [task] = await db
      .select()
      .from(schema.tasks)
      .where(eq(schema.tasks.id, taskId))
      .limit(1);

    if (!task) {
      throw new NotFoundError("Task");
    }

    // Only allow downloading completed prediction tasks
    if (task.type !== "predict") {
      throw new BadRequestError("Only prediction task results can be downloaded");
    }

    if (task.status !== "completed") {
      throw new BadRequestError("Task is not completed yet");
    }

    const result: any = task.result || {};
    const outputFile = result.outputFile || (task.parameter as any)?.outputFile;

    if (!outputFile) {
      throw new NotFoundError("Output file");
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
  });

export default download;
