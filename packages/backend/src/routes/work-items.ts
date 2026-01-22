import { eq } from "drizzle-orm";
import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { z } from "zod";

import {
  CreateWorkItemSchema,
  UpdateWorkItemSchema,
  WorkItemIdParamSchema,
  CreateBatchTrainTaskSchema,
  CreateSingleTrainTaskSchema,
  InlinePredictSchema,
} from "@xenix/shared";

import { authMiddleware, requireAuth } from "../middleware/auth";
import { WorkItemService, DatasetService } from "../services";
import { getMLBackendService } from "../services/MLBackendService";
import { db, schema } from "../database";
import { BadRequestError, NotFoundError } from "../errors";
import logger from "../utils/logger";
import { createStorageService } from "../storage";
import { analyzeFileFromBuffer } from "../utils/datasetUtils";

const workItemService = new WorkItemService();
const datasetService = new DatasetService();

const workItems = new Hono()
  .use("*", authMiddleware)

  // Get all work items
  .get("/", async (c) => {
    const user = requireAuth(c);
    const projectIdQuery = c.req.query("projectId");
    const projectId = projectIdQuery ? Number(projectIdQuery) : undefined;

    const items = await workItemService.getWorkItemsByUser(user.id, projectId);
    return c.json(items);
  })

  // Create work item
  .post("/", zValidator("json", CreateWorkItemSchema), async (c) => {
    const user = requireAuth(c);
    const data = c.req.valid("json");

    const workItem = await workItemService.createWorkItem(user.id, data);
    return c.json(workItem, 201);
  })

  // Get single work item
  .get("/:id", zValidator("param", WorkItemIdParamSchema), async (c) => {
    const user = requireAuth(c);
    const { id: idStr } = c.req.valid("param");
    const id = parseInt(idStr);

    const workItem = await workItemService.getWorkItemById(id, user.id);
    return c.json(workItem);
  })

  // Update work item
  .put(
    "/:id",
    zValidator("param", WorkItemIdParamSchema),
    zValidator("json", UpdateWorkItemSchema),
    async (c) => {
      const user = requireAuth(c);
      const { id: idStr } = c.req.valid("param");
      const id = parseInt(idStr);
      const data = c.req.valid("json");

      const updatedWorkItem = await workItemService.updateWorkItem(
        id,
        user.id,
        data,
      );
      return c.json(updatedWorkItem);
    },
  )

  // Delete work item
  .delete("/:id", zValidator("param", WorkItemIdParamSchema), async (c) => {
    const user = requireAuth(c);
    const { id: idStr } = c.req.valid("param");
    const id = parseInt(idStr);

    await workItemService.deleteWorkItem(id, user.id);
    return c.json({ message: "Work item deleted successfully" });
  })

  // ===== ML OPERATIONS =====
  // All ML operations are scoped under work items and require mlBackendDeploymentId

  // Batch train endpoint
  .post(
    "/:id/train/batch",
    zValidator("param", WorkItemIdParamSchema),
    zValidator("json", CreateBatchTrainTaskSchema),
    async (c) => {
      const user = requireAuth(c);
      const { id: idStr } = c.req.valid("param");
      const workItemId = parseInt(idStr);
      let { datasetId, featureColumns, targetColumn, model, paramGrid } =
        c.req.valid("json");

      // Load work item and validate ownership
      const [workItem] = await db
        .select()
        .from(schema.workItems)
        .where(eq(schema.workItems.id, workItemId))
        .limit(1);

      if (!workItem) {
        throw new NotFoundError("Work item");
      }

      // Validate ML backend deployment is selected
      if (!workItem.mlBackendDeploymentId) {
        throw new BadRequestError(
          "ML backend deployment must be selected for this work item before starting ML operations",
        );
      }

      // Fill missing values from work item
      if (!datasetId && workItem.datasetId) datasetId = workItem.datasetId;
      if (
        (!featureColumns || featureColumns.length === 0) &&
        workItem.featureColumns
      ) {
        featureColumns = workItem.featureColumns as string[];
      }
      if (!targetColumn && workItem.targetColumn)
        targetColumn = workItem.targetColumn as string;

      // Validate required parameters
      if (!datasetId) {
        throw new BadRequestError("datasetId is required");
      }

      if (!featureColumns || featureColumns.length === 0) {
        throw new BadRequestError(
          "featureColumns array is required and must not be empty",
        );
      }

      if (!targetColumn) {
        throw new BadRequestError("targetColumn is required");
      }

      // Verify dataset exists
      const [dataset] = await db
        .select()
        .from(schema.datasets)
        .where(eq(schema.datasets.id, datasetId))
        .limit(1);

      if (!dataset) {
        throw new NotFoundError("Dataset");
      }

      // Get deployment to determine storage type
      const [deployment] = await db
        .select()
        .from(schema.mlBackendDeployments)
        .where(
          eq(schema.mlBackendDeployments.id, workItem.mlBackendDeploymentId),
        )
        .limit(1);

      if (!deployment) {
        throw new NotFoundError("ML Backend Deployment");
      }

      const mlService = getMLBackendService();

      // Get train data path based on storage type
      const trainDataPath =
        deployment.storage === "oss"
          ? createStorageService().getFilesystemPath(dataset.filePath)
          : dataset.filePath;

      // Create task record
      const [insertedTask] = await db
        .insert(schema.tasks)
        .values({
          workItemId,
          mlBackendDeploymentId: workItem.mlBackendDeploymentId,
          type: "batch-train",
          status: "pending",
          parameter: {
            model,
            datasetId,
            featureColumns,
            targetColumn,
            paramGrid,
          },
        })
        .returning();

      // Fire ml-backend request
      const mlRequest = mlService.batchTrain(
        workItem.mlBackendDeploymentId,
        insertedTask.id,
        {
          trainDataPath,
          model,
          featureColumns,
          targetColumn,
          paramGrid,
        },
      );

      // Wait 5s to check for errors
      let hasError = false;
      let errorMessage = "";
      await Promise.race([
        mlRequest.catch((error) => {
          hasError = true;
          errorMessage = error.message;
          logger.error(
            { error: error.message, taskId: insertedTask.id },
            "ML backend request failed",
          );
          throw error;
        }),
        new Promise((resolve) => setTimeout(resolve, 5000)),
      ]);

      // Update task status
      if (hasError) {
        await db
          .update(schema.tasks)
          .set({
            status: "failed",
            error: errorMessage,
            endAt: new Date(),
          })
          .where(eq(schema.tasks.id, insertedTask.id));
      } else {
        await db
          .update(schema.tasks)
          .set({ status: "running" })
          .where(eq(schema.tasks.id, insertedTask.id));
      }

      return c.json(
        {
          taskId: insertedTask.id,
          message: "Batch training started",
        },
        201,
      );
    },
  )

  // Single train endpoint
  .post(
    "/:id/train/single",
    zValidator("param", WorkItemIdParamSchema),
    zValidator("json", CreateSingleTrainTaskSchema),
    async (c) => {
      const user = requireAuth(c);
      const { id: idStr } = c.req.valid("param");
      const workItemId = parseInt(idStr);
      let { datasetId, featureColumns, targetColumn, model, parameters } =
        c.req.valid("json");

      // Load work item
      const [workItem] = await db
        .select()
        .from(schema.workItems)
        .where(eq(schema.workItems.id, workItemId))
        .limit(1);

      if (!workItem) {
        throw new NotFoundError("Work item");
      }

      // Validate ML backend deployment is selected
      if (!workItem.mlBackendDeploymentId) {
        throw new BadRequestError(
          "ML backend deployment must be selected for this work item before starting ML operations",
        );
      }

      // Fill missing values from work item
      if (!datasetId && workItem.datasetId) datasetId = workItem.datasetId;
      if (
        (!featureColumns || featureColumns.length === 0) &&
        workItem.featureColumns
      ) {
        featureColumns = workItem.featureColumns as string[];
      }
      if (!targetColumn && workItem.targetColumn)
        targetColumn = workItem.targetColumn as string;

      // Validate required parameters
      if (!datasetId) {
        throw new BadRequestError("datasetId is required");
      }

      if (!featureColumns || featureColumns.length === 0) {
        throw new BadRequestError(
          "featureColumns array is required and must not be empty",
        );
      }

      if (!targetColumn) {
        throw new BadRequestError("targetColumn is required");
      }

      // Verify dataset exists
      const [dataset] = await db
        .select()
        .from(schema.datasets)
        .where(eq(schema.datasets.id, datasetId))
        .limit(1);

      if (!dataset) {
        throw new NotFoundError("Dataset");
      }

      // Get deployment to determine storage type
      const [deployment] = await db
        .select()
        .from(schema.mlBackendDeployments)
        .where(
          eq(schema.mlBackendDeployments.id, workItem.mlBackendDeploymentId),
        )
        .limit(1);

      if (!deployment) {
        throw new NotFoundError("ML Backend Deployment");
      }

      const mlService = getMLBackendService();

      // Get train data path based on storage type
      const trainDataPath =
        deployment.storage === "oss"
          ? createStorageService().getFilesystemPath(dataset.filePath)
          : dataset.filePath;

      // Create task record
      const [insertedTask] = await db
        .insert(schema.tasks)
        .values({
          workItemId,
          mlBackendDeploymentId: workItem.mlBackendDeploymentId,
          type: "single-train",
          status: "pending",
          parameter: {
            model,
            datasetId,
            featureColumns,
            targetColumn,
            parameters,
          },
        })
        .returning();

      // Fire ml-backend request
      const mlRequest = mlService.singleTrain(
        workItem.mlBackendDeploymentId,
        insertedTask.id,
        {
          trainDataPath,
          model,
          featureColumns,
          targetColumn,
          params: parameters,
        },
      );

      // Wait 5s to check for errors
      let hasError = false;
      let errorMessage = "";
      await Promise.race([
        mlRequest.catch((error) => {
          hasError = true;
          errorMessage = error.message;
          logger.error(
            { error: error.message, taskId: insertedTask.id },
            "ML backend request failed",
          );
          throw error;
        }),
        new Promise((resolve) => setTimeout(resolve, 5000)),
      ]);

      // Update task status
      if (hasError) {
        await db
          .update(schema.tasks)
          .set({
            status: "failed",
            error: errorMessage,
            endAt: new Date(),
          })
          .where(eq(schema.tasks.id, insertedTask.id));
      } else {
        await db
          .update(schema.tasks)
          .set({ status: "running" })
          .where(eq(schema.tasks.id, insertedTask.id));
      }

      return c.json(
        {
          taskId: insertedTask.id,
          message: "Single training started",
        },
        201,
      );
    },
  )

  // Inline prediction endpoint
  .post(
    "/:id/predict/inline",
    zValidator("param", WorkItemIdParamSchema),
    zValidator("json", InlinePredictSchema),
    async (c) => {
      const user = requireAuth(c);
      const { id: idStr } = c.req.valid("param");
      const workItemId = parseInt(idStr);
      const { predictionData, model, tuningTaskId } = c.req.valid("json");

      // Load work item
      const [workItem] = await db
        .select()
        .from(schema.workItems)
        .where(eq(schema.workItems.id, workItemId))
        .limit(1);

      if (!workItem) {
        throw new NotFoundError("Work item");
      }

      // Validate ML backend deployment is selected
      if (!workItem.mlBackendDeploymentId) {
        throw new BadRequestError(
          "ML backend deployment must be selected for this work item before starting ML operations",
        );
      }

      if (!workItem.datasetId) {
        throw new BadRequestError("Work item does not have a training dataset");
      }

      if (!workItem.featureColumns || !workItem.targetColumn) {
        throw new BadRequestError(
          "Work item does not have feature columns or target column configured",
        );
      }

      const featureColumns = workItem.featureColumns as string[];
      const targetColumn = workItem.targetColumn as string;

      // Validate prediction data
      for (let i = 0; i < predictionData.length; i++) {
        const item = predictionData[i];
        for (const col of featureColumns) {
          if (!(col in item)) {
            throw new BadRequestError(
              `Item at index ${i} is missing required feature column: ${col}`,
            );
          }
        }
      }

      // Load training dataset
      const [trainingDataset] = await db
        .select()
        .from(schema.datasets)
        .where(eq(schema.datasets.id, workItem.datasetId))
        .limit(1);

      if (!trainingDataset) {
        throw new NotFoundError("Training dataset");
      }

      // Get deployment to determine storage type
      const [deployment] = await db
        .select()
        .from(schema.mlBackendDeployments)
        .where(
          eq(schema.mlBackendDeployments.id, workItem.mlBackendDeploymentId),
        )
        .limit(1);

      if (!deployment) {
        throw new NotFoundError("ML Backend Deployment");
      }

      // Determine train data path based on deployment storage type
      const trainDataPath =
        deployment.storage === "oss"
          ? createStorageService().getFilesystemPath(trainingDataset.filePath)
          : trainingDataset.filePath;

      // Load tuning task to get params
      const [tuningTask] = await db
        .select()
        .from(schema.tasks)
        .where(eq(schema.tasks.id, tuningTaskId))
        .limit(1);

      if (!tuningTask || !tuningTask.result) {
        throw new NotFoundError("Tuning results for the specified task ID");
      }

      const result: any = tuningTask.result;
      const params = result.bestParams || result.params || {};

      const mlService = getMLBackendService();

      // Create task record
      const [insertedTask] = await db
        .insert(schema.tasks)
        .values({
          workItemId,
          mlBackendDeploymentId: workItem.mlBackendDeploymentId,
          type: "predict-inline",
          status: "pending",
          parameter: {
            model,
            trainingDatasetId: workItem.datasetId,
            featureColumns,
            targetColumn,
            tuningTaskId,
            predictionDataCount: predictionData.length,
          },
        })
        .returning();

      // Execute prediction via ML backend
      const mlRequest = mlService.predictInline(
        workItem.mlBackendDeploymentId,
        insertedTask.id,
        {
          trainDataPath,
          toPredictData: predictionData,
          model,
          params,
          featureColumns,
          targetColumn,
        },
      );

      // Wait 5s to check for errors
      let hasError = false;
      let errorMessage = "";
      await Promise.race([
        mlRequest.catch((error) => {
          hasError = true;
          errorMessage = error.message;
          logger.error(
            { error: error.message, taskId: insertedTask.id },
            "ML backend request failed",
          );
          throw error;
        }),
        new Promise((resolve) => setTimeout(resolve, 5000)),
      ]);

      // Update task status
      if (hasError) {
        await db
          .update(schema.tasks)
          .set({
            status: "failed",
            error: errorMessage,
            endAt: new Date(),
          })
          .where(eq(schema.tasks.id, insertedTask.id));
      } else {
        await db
          .update(schema.tasks)
          .set({ status: "running" })
          .where(eq(schema.tasks.id, insertedTask.id));
      }

      return c.json(
        {
          taskId: insertedTask.id,
          message: "Inline prediction started",
        },
        201,
      );
    },
  )

  // File-based prediction endpoint
  .post(
    "/:id/predict/file",
    zValidator("param", WorkItemIdParamSchema),
    async (c) => {
      const user = requireAuth(c);
      const { id: idStr } = c.req.valid("param");
      const workItemId = parseInt(idStr);

      const formData = await c.req.formData();
      const file = formData.get("file") as File;
      const filePath = formData.get("filePath") as string;
      const fileName = formData.get("fileName") as string;
      const fileSizeStr = formData.get("fileSize") as string;
      const columnsStr = formData.get("columns") as string;
      const rowCountStr = formData.get("rowCount") as string;
      const model = formData.get("model") as string;
      const tuningTaskIdStr = formData.get("tuningTaskId") as string;

      if (!model || !tuningTaskIdStr) {
        throw new BadRequestError(
          "Missing required fields: model or tuningTaskId",
        );
      }

      const tuningTaskId = Number(tuningTaskIdStr);

      // Load work item
      const [workItem] = await db
        .select()
        .from(schema.workItems)
        .where(eq(schema.workItems.id, workItemId))
        .limit(1);

      if (!workItem) {
        throw new NotFoundError("Work item");
      }

      // Validate ML backend deployment is selected
      if (!workItem.mlBackendDeploymentId) {
        throw new BadRequestError(
          "ML backend deployment must be selected for this work item before starting ML operations",
        );
      }

      if (!workItem.datasetId) {
        throw new BadRequestError("Work item does not have a training dataset");
      }

      if (!workItem.featureColumns || !workItem.targetColumn) {
        throw new BadRequestError(
          "Work item does not have feature columns or target column configured",
        );
      }

      const featureColumns = workItem.featureColumns as string[];
      const targetColumn = workItem.targetColumn as string;

      // Load training dataset
      const [trainingDataset] = await db
        .select()
        .from(schema.datasets)
        .where(eq(schema.datasets.id, workItem.datasetId))
        .limit(1);

      if (!trainingDataset) {
        throw new NotFoundError("Training dataset");
      }

      // Get deployment to determine storage type
      const [deployment] = await db
        .select()
        .from(schema.mlBackendDeployments)
        .where(
          eq(schema.mlBackendDeployments.id, workItem.mlBackendDeploymentId),
        )
        .limit(1);

      if (!deployment) {
        throw new NotFoundError("ML Backend Deployment");
      }

      // Determine train data path based on deployment storage type
      const trainDataPath =
        deployment.storage === "oss"
          ? createStorageService().getFilesystemPath(trainingDataset.filePath)
          : trainingDataset.filePath;

      // Load tuning task to get params
      const [tuningTask] = await db
        .select()
        .from(schema.tasks)
        .where(eq(schema.tasks.id, tuningTaskId))
        .limit(1);

      if (!tuningTask || !tuningTask.result) {
        throw new NotFoundError("Tuning results for the specified task ID");
      }

      const result: any = tuningTask.result;
      const params = result.bestParams || result.params || {};

      let predictionDataset;

      if (deployment.storage === "oss") {
        // Extract metadata from uploaded file
        const buffer = await file.arrayBuffer();
        const { columns, rowCount } = await analyzeFileFromBuffer(
          buffer,
          file.name,
        );

        // Save uploaded prediction file as a dataset
        const datasetsDir = createStorageService().getFilesystemPath("datasets");
        predictionDataset = await datasetService.createDataset(
          file,
          `Prediction Input - ${file.name}`,
          `Prediction input for work item ${workItemId}`,
          null,
          datasetsDir,
          columns,
          rowCount,
        );
      } else {
        // For local storage, create dataset record with provided file path
        const columns = JSON.parse(columnsStr);
        const rowCount = parseInt(rowCountStr);
        const fileSize = parseInt(fileSizeStr);

        predictionDataset = await datasetService.createDatasetFromOSSKey({
          key: filePath,
          name: `Prediction Input - ${fileName}`,
          description: `Prediction input for work item ${workItemId}`,
          projectId: null,
          fileSize,
          columns,
          rowCount,
        });
      }

      // Get the prediction data path
      const toPredictDataPath =
        deployment.storage === "oss"
          ? createStorageService().getFilesystemPath(predictionDataset.filePath)
          : predictionDataset.filePath;

      const mlService = getMLBackendService();

      // Create task record
      const [insertedTask] = await db
        .insert(schema.tasks)
        .values({
          workItemId,
          mlBackendDeploymentId: workItem.mlBackendDeploymentId,
          type: "predict-file",
          status: "pending",
          parameter: {
            model,
            trainingDatasetId: workItem.datasetId,
            predictionDatasetId: predictionDataset.id,
            featureColumns,
            targetColumn,
            tuningTaskId,
          },
        })
        .returning();

      // Fire ml-backend request
      const mlRequest = mlService.predictFile(
        workItem.mlBackendDeploymentId,
        insertedTask.id,
        {
          trainDataPath,
          toPredictDataPath,
          model,
          params,
          featureColumns,
          targetColumn,
        },
      );

      // Wait 5s to check for errors
      let hasError = false;
      let errorMessage = "";
      await Promise.race([
        mlRequest.catch((error) => {
          hasError = true;
          errorMessage = error.message;
          logger.error(
            { error: error.message, taskId: insertedTask.id },
            "ML backend request failed",
          );
          throw error;
        }),
        new Promise((resolve) => setTimeout(resolve, 5000)),
      ]);

      // Update task status
      if (hasError) {
        await db
          .update(schema.tasks)
          .set({
            status: "failed",
            error: errorMessage,
            endAt: new Date(),
          })
          .where(eq(schema.tasks.id, insertedTask.id));
      } else {
        await db
          .update(schema.tasks)
          .set({ status: "running" })
          .where(eq(schema.tasks.id, insertedTask.id));
      }

      return c.json(
        {
          taskId: insertedTask.id,
          message: "File prediction started",
        },
        201,
      );
    },
  );

export default workItems;
