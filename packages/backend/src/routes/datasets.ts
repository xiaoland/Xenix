import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { z } from "zod";
import crypto from "crypto";

import { DatasetIdParamSchema } from "@xenix/shared";

import { BadRequestError } from "../errors";
import { authMiddleware } from "../middleware/auth";
import { DatasetService } from "../services";
import { parseDatasetColumns, analyzeFileFromBuffer } from "../utils/datasetUtils";
import { createStorageService } from "../storage";

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

  // Upload dataset file to OSS
  .post("/upload", async (c) => {
    // 1. Parse FormData
    const formData = await c.req.formData();
    const file = formData.get("file") as File;
    const name = formData.get("name") as string;
    const projectIdStr = formData.get("projectId") as string;

    // 2. Validate inputs
    if (!file || !name) {
      throw new BadRequestError("Missing required fields: file or name");
    }

    const projectId = projectIdStr ? parseInt(projectIdStr) : null;

    // 3. Generate OSS key with UUID
    const uuid = crypto.randomUUID();
    const ext = file.name.split(".").pop() ?? "";
    const key = ext ? `datasets/${uuid}.${ext}` : `datasets/${uuid}`;

    // 4. Convert file to buffer
    const buffer = await file.arrayBuffer();

    // 5. Extract metadata from buffer (fail fast on invalid files)
    const { columns, rowCount } = await analyzeFileFromBuffer(buffer, file.name);

    // 6. Upload to storage using filesystem
    const storage = createStorageService();
    await storage.upload(key, buffer, file.type);

    // 7. Create dataset record in database
    const dataset = await datasetService.createDatasetFromOSSKey({
      key,
      name,
      description: null,
      projectId,
      fileSize: file.size,
      columns,
      rowCount,
    });

    // 8. Return created dataset
    return c.json(
      {
        ...dataset,
        columns: parseDatasetColumns(dataset.columns),
      },
      201
    );
  })

  // Create dataset from local filesystem path
  .post("/confirm-upload", async (c) => {
    const body = await c.req.json();

    // Validate request - only for local storage
    const validated = z.object({
      key: z.string(),
      name: z.string(),
      projectId: z.number().nullable(),
      fileSize: z.number(),
      columns: z.array(z.string()),
      rowCount: z.number(),
      storage: z.enum(["local"]),
    }).parse(body);

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
