/**
 * Work Item Repository
 * Handles database operations for work items
 */
import { desc, eq, inArray } from 'drizzle-orm';

import { db, schema } from '../database/index.js';
import { BaseRepository } from './BaseRepository.js';

type WorkItem = typeof schema.workItems.$inferSelect;

export class WorkItemRepository extends BaseRepository<WorkItem> {
  constructor() {
    super(schema.workItems);
  }

  async findByProject(projectId: number) {
    return await db
      .select()
      .from(schema.workItems)
      .where(eq(schema.workItems.projectId, projectId))
      .orderBy(desc(schema.workItems.createdAt));
  }

  async findByProjects(projectIds: number[]) {
    if (projectIds.length === 0) return [];

    return await db
      .select()
      .from(schema.workItems)
      .where(inArray(schema.workItems.projectId, projectIds))
      .orderBy(desc(schema.workItems.createdAt));
  }

  async findByIdWithProject(id: number) {
    const results = await db
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

    return results[0] || null;
  }
}
