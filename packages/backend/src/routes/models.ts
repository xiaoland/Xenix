import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";

import { ModelIdParamSchema } from "@xenix/shared";

import { authMiddleware } from "../middleware/auth";
import { ModelService } from "../services";

const modelService = new ModelService();

const models = new Hono()
  .use("*", authMiddleware)

  // Get all models
  .get("/", async (c) => {
    const modelsList = await modelService.getAllModels();
    return c.json(modelsList);
  })

  // Get single model by name
  .get("/:id", zValidator("param", ModelIdParamSchema), async (c) => {
    const { id } = c.req.valid("param");
    const model = await modelService.getModelByName(id);
    return c.json(model);
  })

  // Sync model metadata
  .post("/sync", async (c) => {
    const result = await modelService.syncModels();
    return c.json(result);
  });

export default models;
