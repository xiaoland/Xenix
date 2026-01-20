import { Hono } from "hono";

import { authMiddleware } from "../middleware/auth";
import { MLBackendDeploymentService } from "../services";

const deploymentService = new MLBackendDeploymentService();

const mlBackendDeployments = new Hono()
  .use("*", authMiddleware)

  // Get all deployments available to the current user (public + user's private ones)
  .get("/", async (c) => {
    const userId = c.get("userId");
    const deployments = await deploymentService.getAvailableDeployments(userId);

    return c.json(deployments);
  });

export default mlBackendDeployments;
