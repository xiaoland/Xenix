import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { cors } from "hono/cors";
import { logger as honoLogger } from "hono/logger";
import { prettyJSON } from "hono/pretty-json";
import fs from "fs";

import { config } from "./config";
import { errorHandler } from "./middleware/errorHandler";
// Routes
import authRoutes from "./routes/auth";
import codeExecutionRoutes from "./routes/code-execution";
import datasetsRoutes from "./routes/datasets";
import mlBackendDeploymentsRoutes from "./routes/ml-backend-deployments";
import modelsRoutes from "./routes/models";
import obsrvRoutes from "./routes/obsrv";
import projectsRoutes from "./routes/projects";
import tasksRoutes from "./routes/tasks";
import workItemsRoutes from "./routes/work-items";
import logger from "./utils/logger";

// Ensure upload directory exists
if (!fs.existsSync(config.STORAGE_BASE_PATH)) {
  fs.mkdirSync(config.STORAGE_BASE_PATH, { recursive: true });
  logger.info(
    { uploadDir: config.STORAGE_BASE_PATH },
    "Created upload directory",
  );
}

const app = new Hono();

// Middleware
app.use("*", honoLogger());
app.use("*", prettyJSON());
app.use(
  "*",
  cors({
    origin: config.FRONTEND_URL,
    credentials: true,
  }),
);

// API Routes
const routes = app
  .get("/health", (c) =>
    c.json({
      status: "ok",
      timestamp: new Date().toISOString(),
      environment: config.NODE_ENV,
      version: process.env.FC_FUNCTION_VERSION || "dev",
    }),
  )
  .route("/auth", authRoutes)
  .route("/projects", projectsRoutes)
  .route("/work-items", workItemsRoutes)
  .route("/data", datasetsRoutes)
  .route("/models", modelsRoutes)
  .route("/tasks", tasksRoutes)
  .route("/ml-backend-deployments", mlBackendDeploymentsRoutes)
  .route("/code-execution", codeExecutionRoutes)
  .route("/obsrv", obsrvRoutes);

// Error handler (must be last)
app.onError(errorHandler);

logger.info(
  { port: config.BACKEND_PORT, env: config.NODE_ENV },
  "Starting server",
);

serve({
  fetch: app.fetch,
  port: config.BACKEND_PORT,
});

export default app;

// Export type for Hono RPC client
export type AppType = typeof routes;
