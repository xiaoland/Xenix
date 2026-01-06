import { Hono } from "hono";
import { zValidator } from "@hono/zod-validator";
import { db, schema } from "../database/index.js";
import { desc, eq, inArray } from "drizzle-orm";
import { authMiddleware, requireAuth } from "../middleware/auth.js";
import {
  CreateWorkItemSchema,
  UpdateWorkItemSchema,
} from "@xenix/shared";
import {
  NotFoundError,
  BadRequestError,
  ForbiddenError,
} from "../errors/index.js";
import logger from "../utils/logger/index.js";

const workItems = new Hono()
  .use("*", authMiddleware)

  // Get all work items
  .get("/", async (c) => {
    const user = requireAuth(c);
    const projectId = c.req.query("projectId");

    // Get all project IDs owned by the current user
    const userProjects = await db
      .select({ id: schema.projects.id })
      .from(schema.projects)
      .where(eq(schema.projects.createdBy, user.id));

    const userProjectIds = userProjects.map((p) => p.id);

    if (userProjectIds.length === 0) {
      return c.json([]);
    }

    let workItemsQuery = db.select().from(schema.workItems);

    // Filter by project if projectId is provided
    if (projectId) {
      const projectIdNum = Number(projectId);
      if (!isNaN(projectIdNum)) {
        // Check if the project belongs to the user
        if (!userProjectIds.includes(projectIdNum)) {
          throw new ForbiddenError("Access denied");
        }
        workItemsQuery = workItemsQuery.where(
          eq(schema.workItems.projectId, projectIdNum)
        ) as any;
      }
    } else {
      // Return work items from all user's projects
      workItemsQuery = workItemsQuery.where(
        inArray(schema.workItems.projectId, userProjectIds)
      ) as any;
    }

    const items = await workItemsQuery.orderBy(
      desc(schema.workItems.createdAt)
    );

    return c.json(items);
  })

  // Create work item
  .post("/", zValidator("json", CreateWorkItemSchema), async (c) => {
    const user = requireAuth(c);
    const { name, description, projectId } = c.req.valid("json");

    // Verify project exists and belongs to the current user
    const [project] = await db
      .select()
      .from(schema.projects)
      .where(eq(schema.projects.id, projectId))
      .limit(1);

    if (!project) {
      throw new NotFoundError("Project");
    }

    if (project.createdBy !== user.id) {
      throw new ForbiddenError("Access denied");
    }

    // Create work item record
    const [workItem] = await db
      .insert(schema.workItems)
      .values({
        projectId,
        name,
        description: description || null,
        status: "active",
      })
      .returning();

    return c.json(workItem, 201);
  })

  // Get single work item
  .get("/:id", async (c) => {
    const user = requireAuth(c);
    const id = parseInt(c.req.param("id"));

    if (isNaN(id)) {
      throw new BadRequestError("Invalid work item ID");
    }

    const workItemsResult = await db
      .select({
        workItem: schema.workItems,
        projectCreatedBy: schema.projects.createdBy,
      })
      .from(schema.workItems)
      .innerJoin(
        schema.projects,
        eq(schema.workItems.projectId, schema.projects.id)
      )
      .where(eq(schema.workItems.id, id))
      .limit(1);

    if (workItemsResult.length === 0) {
      throw new NotFoundError("Work item");
    }

    const { workItem, projectCreatedBy } = workItemsResult[0];

    // Check if the work item's project belongs to the current user
    if (projectCreatedBy !== user.id) {
      throw new ForbiddenError("Access denied");
    }

    return c.json(workItem);
  })

  // Update work item
  .put("/:id", zValidator("json", UpdateWorkItemSchema), async (c) => {
    const user = requireAuth(c);
    const id = parseInt(c.req.param("id"));
    const updateData = c.req.valid("json");

    if (isNaN(id)) {
      throw new BadRequestError("Invalid work item ID");
    }

    // Check if the work item exists and belongs to a project owned by the current user
    const workItemsResult = await db
      .select({
        workItem: schema.workItems,
        projectCreatedBy: schema.projects.createdBy,
      })
      .from(schema.workItems)
      .innerJoin(
        schema.projects,
        eq(schema.workItems.projectId, schema.projects.id)
      )
      .where(eq(schema.workItems.id, id))
      .limit(1);

    if (workItemsResult.length === 0) {
      throw new NotFoundError("Work item");
    }

    const { projectCreatedBy } = workItemsResult[0];

    if (projectCreatedBy !== user.id) {
      throw new ForbiddenError("Access denied");
    }

    const [updatedWorkItem] = await db
      .update(schema.workItems)
      .set({
        ...updateData,
        updatedAt: new Date(),
      })
      .where(eq(schema.workItems.id, id))
      .returning();

    return c.json(updatedWorkItem);
  })

  // Delete work item
  .delete("/:id", async (c) => {
    const user = requireAuth(c);
    const id = parseInt(c.req.param("id"));

    if (isNaN(id)) {
      throw new BadRequestError("Invalid work item ID");
    }

    // Check if the work item exists and belongs to a project owned by the current user
    const workItemsResult = await db
      .select({
        workItem: schema.workItems,
        projectCreatedBy: schema.projects.createdBy,
      })
      .from(schema.workItems)
      .innerJoin(
        schema.projects,
        eq(schema.workItems.projectId, schema.projects.id)
      )
      .where(eq(schema.workItems.id, id))
      .limit(1);

    if (workItemsResult.length === 0) {
      throw new NotFoundError("Work item");
    }

    const { projectCreatedBy } = workItemsResult[0];

    if (projectCreatedBy !== user.id) {
      throw new ForbiddenError("Access denied");
    }

    // Delete work item (cascades to tasks due to FK if configured)
    await db.delete(schema.workItems).where(eq(schema.workItems.id, id));

    return c.json({ message: "Work item deleted successfully" });
  });

export default workItems;
