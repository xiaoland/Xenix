import path from "path";

import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";

import { DatasetIdParamSchema } from "@xenix/shared";

import { BadRequestError } from "../errors";
import { authMiddleware } from "../middleware/auth";
import { DatasetService } from "../services";
import { parseDatasetColumns } from "../utils/datasetUtils";

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

    if (!name) {
      throw new BadRequestError("Dataset name is required");
    }

    // Get datasets directory path
    const datasetsDir = path.join(process.cwd(), "datasets");

    // Create dataset using service
    const dataset = await datasetService.createDataset(
      file,
      name,
      description,
      projectId,
      datasetsDir
    );

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
