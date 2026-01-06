import { Hono } from "hono";
import { zValidator } from "@hono/zod-validator";
import { db, schema } from "../database/index.js";
import { desc, eq } from "drizzle-orm";
import { authMiddleware } from "../middleware/auth.js";
import {
  parseDatasetColumns,
  analyzeExcelFile,
} from "../utils/datasetUtils.js";
import { validateExcelFile, saveUploadedFile } from "../utils/taskUtils.js";
import {
  NotFoundError,
  BadRequestError,
} from "../errors/index.js";
import { DatasetIdParamSchema } from "@xenix/shared";
import logger from "../utils/logger/index.js";
import path from "path";
import fs from "fs/promises";

const datasets = new Hono()
  .use("*", authMiddleware)

  // Get all datasets
  .get("/", async (c) => {
    // Fetch all datasets, ordered by most recent first
    const datasetsList = await db
      .select()
      .from(schema.datasets)
      .orderBy(desc(schema.datasets.createdAt));

    // Parse columns field for each dataset using utility function
    const datasetsWithParsedColumns = datasetsList.map((dataset) => ({
      ...dataset,
      columns: parseDatasetColumns(dataset.columns),
    }));

    return c.json(datasetsWithParsedColumns);
  })

  // Upload dataset
  .post("/", async (c) => {
    const formData = await c.req.formData();
    const file = formData.get("file") as File;
    const name = formData.get("name") as string;
    const description = (formData.get("description") as string) || null;
    const projectIdStr = (formData.get("projectId") as string) || null;
    const projectId = projectIdStr ? Number(projectIdStr) : null;

    if (!file) {
      throw new BadRequestError("No file uploaded");
    }

    if (!validateExcelFile(file.name)) {
      throw new BadRequestError(
        "Invalid file type. Only Excel files (.xlsx, .xls) are allowed."
      );
    }

    if (!name) {
      throw new BadRequestError("Dataset name is required");
    }

    // Save uploaded file to datasets directory
    const datasetsDir = path.join(process.cwd(), "datasets");
    const filePath = await saveUploadedFile(file, datasetsDir);

    // Get file stats
    const stats = await fs.stat(filePath);
    const fileSize = stats.size;

    // Analyze the Excel file to get columns and row count
    const { columns, rowCount } = await analyzeExcelFile(filePath);

    // Create dataset record with optional project link
    const [dataset] = await db
      .insert(schema.datasets)
      .values({
        projectId: projectId && !isNaN(projectId) ? projectId : null,
        name,
        description,
        filePath,
        fileName: file.name,
        fileSize,
        columns: columns, // Store as JSONB directly
        rowCount,
      })
      .returning();

    return c.json(
      {
        ...dataset,
        columns,
      },
      201
    );
  })

  // Get single dataset
  .get("/:id", zValidator("param", DatasetIdParamSchema), async (c) => {
    const { id: idStr } = c.req.valid("param");
    const id = parseInt(idStr);

    // Fetch dataset by ID
    const [dataset] = await db
      .select()
      .from(schema.datasets)
      .where(eq(schema.datasets.id, id))
      .limit(1);

    if (!dataset) {
      throw new NotFoundError("Dataset");
    }

    // Parse columns field using utility function
    const datasetWithParsedColumns = {
      ...dataset,
      columns: parseDatasetColumns(dataset.columns),
    };

    return c.json(datasetWithParsedColumns);
  })

  // Delete dataset
  .delete("/:id", zValidator("param", DatasetIdParamSchema), async (c) => {
    const { id: idStr } = c.req.valid("param");
    const id = parseInt(idStr);

    // Fetch dataset by ID
    const [dataset] = await db
      .select()
      .from(schema.datasets)
      .where(eq(schema.datasets.id, id))
      .limit(1);

    if (!dataset) {
      throw new NotFoundError("Dataset");
    }

    // Delete the file from filesystem if it exists
    try {
      await fs.unlink(dataset.filePath);
    } catch (fileError: any) {
      // Ignore ENOENT (file not found) errors, but log others
      if (fileError.code !== "ENOENT") {
        logger.warn({ error: fileError, filePath: dataset.filePath }, "Failed to delete file");
      }
    }

    // Delete dataset record from database
    await db.delete(schema.datasets).where(eq(schema.datasets.id, id));

    return c.json({
      message: "Dataset deleted successfully",
    });
  });

export default datasets;
