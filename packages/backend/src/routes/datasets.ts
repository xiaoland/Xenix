import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { z } from "zod";
import crypto from "crypto";

import { DatasetIdParamSchema } from "@xenix/shared";

import { BadRequestError } from "../errors";
import { authMiddleware } from "../middleware/auth";
import { DatasetService } from "../services";
import {
  parseDatasetColumns,
  analyzeFileFromBuffer,
  removeDuplicateRowsFromBuffer,
} from "../utils/datasetUtils";
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
    const { columns, rowCount, duplicateCount, duplicateRows } =
      await analyzeFileFromBuffer(buffer, file.name);

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

    // 8. Return created dataset with duplicate info
    return c.json(
      {
        ...dataset,
        columns: parseDatasetColumns(dataset.columns),
        duplicateInfo: {
          duplicateCount,
          duplicateRows: duplicateRows || [],
        },
      },
      201,
    );
  })

  // Create dataset from local filesystem path
  .post("/confirm-upload", async (c) => {
    const body = await c.req.json();

    // Validate request - only for local storage
    const validated = z
      .object({
        key: z.string(),
        name: z.string(),
        projectId: z.number().nullable(),
        fileSize: z.number(),
        columns: z.array(z.string()),
        rowCount: z.number(),
        storage: z.enum(["local"]),
      })
      .parse(body);

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
      201,
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
  })

  // Remove duplicate rows from dataset
  .post(
    "/:id/remove-duplicates",
    zValidator("param", DatasetIdParamSchema),
    async (c) => {
      const { id: idStr } = c.req.valid("param");
      const id = parseInt(idStr);

      // Get the dataset
      const dataset = await datasetService.getDatasetById(id);

      // Get the file from storage using filesystem path
      const storage = createStorageService();
      const filePath = storage.getFilesystemPath(dataset.filePath);
      const fs = await import("fs/promises");
      const fileBuffer = await fs.readFile(filePath);

      // Remove duplicates
      const {
        buffer: cleanedBuffer,
        originalRowCount,
        removedCount,
        newRowCount,
      } = await removeDuplicateRowsFromBuffer(
        fileBuffer.buffer.slice(
          fileBuffer.byteOffset,
          fileBuffer.byteOffset + fileBuffer.byteLength,
        ),
        dataset.filePath,
      );

      // Upload cleaned file back to storage
      const uuid = crypto.randomUUID();
      const ext = dataset.filePath.split(".").pop() ?? "";
      const newKey = ext ? `datasets/${uuid}.${ext}` : `datasets/${uuid}`;

      const bufferToUpload = cleanedBuffer.buffer.slice(
        cleanedBuffer.byteOffset,
        cleanedBuffer.byteOffset + cleanedBuffer.byteLength,
      ) as ArrayBuffer;

      await storage.upload(
        newKey,
        bufferToUpload,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      );

      // Re-analyze the cleaned file to get columns
      const { columns } = await analyzeFileFromBuffer(
        cleanedBuffer.buffer.slice(
          cleanedBuffer.byteOffset,
          cleanedBuffer.byteOffset + cleanedBuffer.byteLength,
        ) as ArrayBuffer,
        newKey,
      );

      // Create new dataset record
      const newDataset = await datasetService.createDatasetFromOSSKey({
        key: newKey,
        name: `${dataset.name} (deduplicated)`,
        description: dataset.description,
        projectId: dataset.projectId,
        fileSize: cleanedBuffer.length,
        columns,
        rowCount: newRowCount,
      });

      return c.json({
        message: "Duplicates removed successfully",
        originalRowCount,
        removedCount,
        newRowCount,
        dataset: {
          ...newDataset,
          columns: parseDatasetColumns(newDataset.columns),
        },
      });
    },
  );

export default datasets;
