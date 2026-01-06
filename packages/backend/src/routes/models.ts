import { Hono } from "hono";
import { HTTPException } from "hono/http-exception";
import { db, schema } from "../database/index.js";
import { eq } from "drizzle-orm";
import { authMiddleware } from "../middleware/auth.js";
import { executePythonScript } from "../utils/pythonExecutor.js";

const models = new Hono()
  .use("*", authMiddleware)

  // Get all models
  .get("/", async (c) => {
    try {
      const modelsList = await db.select().from(schema.modelMetadata);

      return c.json({
        success: true,
        models: modelsList,
        count: modelsList.length,
      });
    } catch (error: any) {
      console.error("Failed to fetch model metadata:", error);
      return c.json({
        success: false,
        error: error.message || "Failed to fetch model metadata",
      });
    }
  })

  // Get single model by name
  .get("/:id", async (c) => {
    try {
      const id = c.req.param("id");

      if (!id) {
        throw new HTTPException(400, { message: "Model name is required" });
      }

      const model = await db
        .select()
        .from(schema.modelMetadata)
        .where(eq(schema.modelMetadata.name, id))
        .limit(1);

      if (model.length === 0) {
        throw new HTTPException(404, { message: "Model not found" });
      }

      return c.json({
        success: true,
        model: model[0],
      });
    } catch (error: any) {
      console.error("Failed to fetch model metadata:", error);
      if (error instanceof HTTPException) {
        throw error;
      }
      throw new HTTPException(500, {
        message: error.message || "Failed to fetch model metadata",
      });
    }
  })

  // Sync model metadata
  .post("/sync", async (c) => {
    try {
      // Execute the Python model scanning script
      const scriptPath = "src/business/ml/scan_models.py";
      const result = await executePythonScript(scriptPath, {});

      if (!result.success) {
        throw new Error(result.error || "Model scanning failed");
      }

      const modelsList = result.models || [];
      let syncedCount = 0;
      let updatedCount = 0;
      let errors: string[] = [];

      // Synchronize each model to the database
      for (const model of modelsList) {
        try {
          // Check if model already exists
          const [existing] = await db
            .select()
            .from(schema.modelMetadata)
            .where(eq(schema.modelMetadata.name, model.name))
            .limit(1);

          if (existing) {
            // Update existing model
            await db
              .update(schema.modelMetadata)
              .set({
                category: model.category,
                label: model.label,
                paramGridSchema: model.param_grid_schema,
                updatedAt: new Date(),
              })
              .where(eq(schema.modelMetadata.name, model.name));
            updatedCount++;
          } else {
            // Insert new model
            await db.insert(schema.modelMetadata).values({
              category: model.category,
              name: model.name,
              label: model.label,
              paramGridSchema: model.param_grid_schema,
            });
            syncedCount++;
          }
        } catch (error: any) {
          errors.push(`Failed to sync ${model.name}: ${error.message}`);
        }
      }

      return c.json({
        success: true,
        message: "Model metadata synchronized successfully",
        synced: syncedCount,
        updated: updatedCount,
        total: modelsList.length,
        errors: errors.length > 0 ? errors : undefined,
      });
    } catch (error: any) {
      console.error("Failed to sync model metadata:", error);
      return c.json({
        success: false,
        error: error.message || "Failed to sync model metadata",
      });
    }
  });

export default models;
