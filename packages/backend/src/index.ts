import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { cors } from "hono/cors";
import { logger as honoLogger } from "hono/logger";
import { prettyJSON } from "hono/pretty-json";

import { config } from "./config";
import { errorHandler } from "./middleware/errorHandler";
// Routes
import authRoutes from "./routes/auth";
import datasetsRoutes from "./routes/datasets";
import downloadRoutes from "./routes/download";
import modelsRoutes from "./routes/models";
import obsrvRoutes from "./routes/obsrv";
import predictRoutes from "./routes/predict";
import projectsRoutes from "./routes/projects";
import tasksRoutes from "./routes/tasks";
import tuneRoutes from "./routes/tune";
import workItemsRoutes from "./routes/work-items";
import logger from "./utils/logger";

const app = new Hono();

// Middleware
app.use("*", honoLogger());
app.use("*", prettyJSON());
app.use(
  "*",
  cors({
    origin: config.FRONTEND_URL,
    credentials: true,
  })
);

// API Routes
const routes = app
  .get("/health", (c) => c.json({ status: "ok" }))
  .route("/auth", authRoutes)
  .route("/projects", projectsRoutes)
  .route("/work-items", workItemsRoutes)
  .route("/data", datasetsRoutes)
  .route("/models", modelsRoutes)
  .route("/tasks", tasksRoutes)
  .route("/tune", tuneRoutes)
  .route("/predict", predictRoutes)
  .route("/download", downloadRoutes)
  .route("/obsrv", obsrvRoutes);

// Error handler (must be last)
app.onError(errorHandler);

logger.info(
  { port: config.BACKEND_PORT, env: config.NODE_ENV },
  "Starting server"
);

serve({
  fetch: app.fetch,
  port: config.BACKEND_PORT,
});

export default app;

// Export type for Hono RPC client
export type AppType = typeof routes;
