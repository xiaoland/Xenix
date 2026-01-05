import { db, schema } from "../../database";
import { desc, eq, inArray } from "drizzle-orm";
import { getCurrentUser, requireAuth } from "../../utils/auth";

export default defineEventHandler(async (event) => {
  try {
    const user = requireAuth(await getCurrentUser(event));
    const query = getQuery(event);
    const projectId = query.projectId ? Number(query.projectId) : undefined;

    // Get all project IDs owned by the current user
    const userProjects = await db
      .select({ id: schema.projects.id })
      .from(schema.projects)
      .where(eq(schema.projects.createdBy, user.id));

    const userProjectIds = userProjects.map((p) => p.id);

    if (userProjectIds.length === 0) {
      return {
        success: true,
        workItems: [],
      };
    }

    let workItemsQuery = db.select().from(schema.workItems);

    // Filter by project if projectId is provided
    if (projectId && !isNaN(projectId)) {
      // Check if the project belongs to the user
      if (!userProjectIds.includes(projectId)) {
        throw createError({
          statusCode: 403,
          message: "Access denied",
        });
      }
      workItemsQuery = workItemsQuery.where(
        eq(schema.workItems.projectId, projectId)
      ) as any;
    } else {
      // Return work items from all user's projects
      workItemsQuery = workItemsQuery.where(
        inArray(schema.workItems.projectId, userProjectIds)
      ) as any;
    }

    const workItems = await workItemsQuery.orderBy(
      desc(schema.workItems.createdAt)
    );

    return {
      success: true,
      workItems,
    };
  } catch (error) {
    console.error("Work items fetch error:", error);
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error ? error.message : "Failed to fetch work items",
    });
  }
});
