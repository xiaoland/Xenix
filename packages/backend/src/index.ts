import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { cors } from "hono/cors";
import { logger } from "hono/logger";
import { prettyJSON } from "hono/pretty-json";

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
app.use("*", logger());
app.use("*", prettyJSON());
app.use(
  "*",
  cors({
    origin: process.env.FRONTEND_URL || "http://localhost:5173",
    credentials: true,
  })
);

// Health check
app.get("/health", (c) => c.json({ status: "ok" }));

// API routes
app.route("/api/auth", authRoutes);
app.route("/api/projects", projectsRoutes);
app.route("/api/work-items", workItemsRoutes);
app.route("/api/data", datasetsRoutes);
app.route("/api/models", modelsRoutes);
app.route("/api/tasks", tasksRoutes);
app.route("/api", tuneRoutes);
app.route("/api/predict", predictRoutes);
app.route("/api/download", downloadRoutes);
app.route("/api/obsrv", obsrvRoutes);

const port = Number(process.env.BACKEND_PORT) || 3000;

console.log(`Starting server on port ${port}...`);

serve({
  fetch: app.fetch,
  port,
});

export default app;

// Export type for Hono RPC client
export type AppType = typeof app;
