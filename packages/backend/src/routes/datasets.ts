import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { z } from "zod";

import { DatasetIdParamSchema } from "@xenix/shared";

import { BadRequestError } from "../errors";
import { authMiddleware } from "../middleware/auth";
import { DatasetService } from "../services";
import { parseDatasetColumns, analyzeExcelFile } from "../utils/datasetUtils";
import { validateExcelFile } from "../utils/taskUtils";
import { storage, presignedUrlRequestSchema } from "../storage";

const datasetService = new DatasetService();

const datasets = new Hono()
  .use("*", authMiddleware)

  // Get all datasets
  .get("/", async (c) => {
    const datasetsList = await datasetService.getAllDatasets();

    // Parse columns field for each dataset
    const datasetsWithParsedColumns = datasetsList.map((dataset) => ({
      ...dataset,
      columns: parseDatasetColumns(dataset.columns),
    }));

    return c.json(datasetsWithParsedColumns);
  })

  // Generate presigned URL for dataset upload
  .post("/upload-url", async (c) => {
    const body = await c.req.json();

    // Validate request
    const validated = presignedUrlRequestSchema.parse(body);

    // Generate presigned URL
    const result = await storage.generatePresignedUploadUrl(validated);

    return c.json(result);
  })

  // Confirm dataset upload to OSS or create local dataset
  .post("/confirm-upload", async (c) => {
    const body = await c.req.json();

    // Validate request - metadata now comes from frontend
    const validated = z.object({
      key: z.string(),
      name: z.string(),
      projectId: z.number().nullable(),
      fileSize: z.number(),
      columns: z.array(z.string()),
      rowCount: z.number(),
      storage: z.enum(["local", "oss"]).default("oss"),
    }).parse(body);

    // For OSS storage, verify file exists
    if (validated.storage === "oss") {
      const fileExists = await storage.exists(validated.key);
      if (!fileExists) {
        throw new BadRequestError("File not found in storage");
      }
    }

    // Create dataset record with provided metadata
    const dataset = await datasetService.createDatasetFromOSSKey({
      key: validated.key,
      name: validated.name,
      description: null,
      projectId: validated.projectId,
      fileSize: validated.fileSize,
      columns: validated.columns,
      rowCount: validated.rowCount,
    });

    return c.json(
      {
        ...dataset,
        columns: parseDatasetColumns(dataset.columns),
      },
      201
    );
  })

  // Get single dataset
  .get("/:id", zValidator("param", DatasetIdParamSchema), async (c) => {
    const { id: idStr } = c.req.valid("param");
    const id = parseInt(idStr);

    const dataset = await datasetService.getDatasetById(id);

    return c.json({
      ...dataset,
      columns: parseDatasetColumns(dataset.columns),
    });
  })

  // Delete dataset
  .delete("/:id", zValidator("param", DatasetIdParamSchema), async (c) => {
    const { id: idStr } = c.req.valid("param");
    const id = parseInt(idStr);

    await datasetService.deleteDataset(id);

    return c.json({
      message: "Dataset deleted successfully",
    });
  });

export default datasets;
