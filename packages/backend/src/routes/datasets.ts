import { Hono } from "hono";
import { HTTPException } from "hono/http-exception";
import { db, schema } from "../database/index.js";
import { desc, eq } from "drizzle-orm";
import { authMiddleware } from "../middleware/auth.js";
import {
  parseDatasetColumns,
  analyzeExcelFile,
} from "../utils/datasetUtils.js";
import { validateExcelFile, saveUploadedFile } from "../utils/taskUtils.js";
import path from "path";
import fs from "fs/promises";

const datasets = new Hono()
  .use("*", authMiddleware)

  // Get all datasets
  .get("/", async (c) => {
    try {
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
    } catch (error) {
      console.error("Datasets fetch error:", error);
      throw new HTTPException(500, {
        message:
          error instanceof Error ? error.message : "Failed to fetch datasets",
      });
    }
  })

  // Upload dataset
  .post("/", async (c) => {
    try {
      const formData = await c.req.formData();
      const file = formData.get("file") as File;
      const name = formData.get("name") as string;
      const description = (formData.get("description") as string) || null;
      const projectIdStr = (formData.get("projectId") as string) || null;
      const projectId = projectIdStr ? Number(projectIdStr) : null;

      if (!file) {
        throw new HTTPException(400, { message: "No file uploaded" });
      }

      if (!validateExcelFile(file.name)) {
        throw new HTTPException(400, {
          message:
            "Invalid file type. Only Excel files (.xlsx, .xls) are allowed.",
        });
      }

      if (!name) {
        throw new HTTPException(400, { message: "Dataset name is required" });
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
      const result = await db
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

      const dataset = result[0];

      return c.json({
        success: true,
        dataset: {
          ...dataset,
          columns,
        },
        message: "Dataset uploaded successfully",
      });
    } catch (error) {
      console.error("Dataset upload error:", error);
      if (error instanceof HTTPException) {
        throw error;
      }
      throw new HTTPException(500, {
        message:
          error instanceof Error ? error.message : "Failed to upload dataset",
      });
    }
  })

  // Get single dataset
  .get("/:id", async (c) => {
    const id = parseInt(c.req.param("id"));

    if (isNaN(id)) {
      throw new HTTPException(400, { message: "Invalid dataset ID" });
    }

    try {
      // Fetch dataset by ID
      const [dataset] = await db
        .select()
        .from(schema.datasets)
        .where(eq(schema.datasets.id, id))
        .limit(1);

      if (!dataset) {
        throw new HTTPException(404, { message: "Dataset not found" });
      }

      // Parse columns field using utility function
      const datasetWithParsedColumns = {
        ...dataset,
        columns: parseDatasetColumns(dataset.columns),
      };

      return c.json({
        success: true,
        dataset: datasetWithParsedColumns,
      });
    } catch (error) {
      console.error("Dataset fetch error:", error);
      if (error instanceof HTTPException) {
        throw error;
      }
      throw new HTTPException(500, {
        message:
          error instanceof Error ? error.message : "Failed to fetch dataset",
      });
    }
  })

  // Delete dataset
  .delete("/:id", async (c) => {
    const id = parseInt(c.req.param("id"));

    if (isNaN(id)) {
      throw new HTTPException(400, { message: "Invalid dataset ID" });
    }

    try {
      // Fetch dataset by ID
      const [dataset] = await db
        .select()
        .from(schema.datasets)
        .where(eq(schema.datasets.id, id))
        .limit(1);

      if (!dataset) {
        throw new HTTPException(404, { message: "Dataset not found" });
      }

      // Delete the file from filesystem if it exists
      try {
        await fs.unlink(dataset.filePath);
      } catch (fileError: any) {
        // Ignore ENOENT (file not found) errors, but log others
        if (fileError.code !== "ENOENT") {
          console.warn("Failed to delete file:", fileError);
        }
      }

      // Delete dataset record from database
      await db.delete(schema.datasets).where(eq(schema.datasets.id, id));

      return c.json({
        success: true,
        message: "Dataset deleted successfully",
      });
    } catch (error) {
      console.error("Dataset deletion error:", error);
      if (error instanceof HTTPException) {
        throw error;
      }
      throw new HTTPException(500, {
        message:
          error instanceof Error ? error.message : "Failed to delete dataset",
      });
    }
  });

export default datasets;
