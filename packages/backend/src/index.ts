import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { cors } from "hono/cors";
import { logger as honoLogger } from "hono/logger";
import { prettyJSON } from "hono/pretty-json";
import { errorHandler } from "./middleware/errorHandler.js";
import { config } from "./config/index.js";
import logger from "./utils/logger/index.js";

// Routes
import authRoutes from "./routes/auth.js";
import projectsRoutes from "./routes/projects.js";
import workItemsRoutes from "./routes/work-items.js";
import datasetsRoutes from "./routes/datasets.js";
import modelsRoutes from "./routes/models.js";
import tasksRoutes from "./routes/tasks.js";
import tuneRoutes from "./routes/tune.js";
import predictRoutes from "./routes/predict.js";
import downloadRoutes from "./routes/download.js";
import obsrvRoutes from "./routes/obsrv.js";

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

logger.info({ port: config.BACKEND_PORT, env: config.NODE_ENV }, 'Starting server');

serve({
  fetch: app.fetch,
  port: config.BACKEND_PORT,
});

export default app;

// Export type for Hono RPC client
export type AppType = typeof routes;
