import { db, schema } from "../../database";
import { analyzeExcelFile } from "../../utils/datasetUtils";
import { validateExcelFile, saveUploadedFile } from "../../utils/taskUtils";
import { eq } from "drizzle-orm";
import path from "path";
import fs from "fs/promises";

export default defineEventHandler(async (event) => {
  try {
    const formData = await readFormData(event);
    const file = formData.get("file") as File;
    const name = formData.get("name") as string;
    const description = (formData.get("description") as string) || null;
    const projectIdStr = (formData.get("projectId") as string) || null;
    const projectId = projectIdStr ? Number(projectIdStr) : null;

    if (!file) {
      throw createError({
        statusCode: 400,
        message: "No file uploaded",
      });
    }

    if (!validateExcelFile(file.name)) {
      throw createError({
        statusCode: 400,
        message:
          "Invalid file type. Only Excel files (.xlsx, .xls) are allowed.",
      });
    }

    if (!name) {
      throw createError({
        statusCode: 400,
        message: "Dataset name is required",
      });
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
    const result = await db.insert(schema.datasets).values({
      projectId: projectId && !isNaN(projectId) ? projectId : null,
      name,
      description,
      filePath,
      fileName: file.name,
      fileSize,
      columns: columns, // Store as JSONB directly
      rowCount,
    }).returning();

    const dataset = result[0];

    return {
      success: true,
      dataset: {
        ...dataset,
        columns,
      },
      message: "Dataset uploaded successfully",
    };
  } catch (error) {
    console.error("Dataset upload error:", error);
    // Re-throw createError objects directly
    if (error && typeof error === "object" && "statusCode" in error) {
      throw error;
    }
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error ? error.message : "Failed to upload dataset",
    });
  }
});
