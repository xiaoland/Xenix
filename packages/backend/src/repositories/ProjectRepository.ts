/**
 * Project Repository
 * Handles database operations for projects
 */
import { desc, eq } from 'drizzle-orm';

import { db, schema } from '../database/index.js';
import { BaseRepository } from './BaseRepository.js';

type Project = typeof schema.projects.$inferSelect;

export class ProjectRepository extends BaseRepository<Project> {
  constructor() {
    super(schema.projects);
  }

  async findByUser(userId: string) {
    return await db
      .select()
      .from(schema.projects)
      .where(eq(schema.projects.createdBy, userId))
      .orderBy(desc(schema.projects.createdAt));
  }

  async findByIdWithRelations(id: number) {
    const [project] = await db
      .select()
      .from(schema.projects)
      .where(eq(schema.projects.id, id))
      .limit(1);

    if (!project) return null;

    const workItems = await db
      .select()
      .from(schema.workItems)
      .where(eq(schema.workItems.projectId, id));

    const datasets = await db
      .select()
      .from(schema.datasets)
      .where(eq(schema.datasets.projectId, id));

    return {
      ...project,
      workItems,
      datasets,
    };
  }

  async findAllWithRelations(userId: string) {
    const projectsList = await this.findByUser(userId);

    return await Promise.all(
      projectsList.map(async (project) => {
        const workItems = await db
          .select()
          .from(schema.workItems)
          .where(eq(schema.workItems.projectId, project.id));

        const datasets = await db
          .select()
          .from(schema.datasets)
          .where(eq(schema.datasets.projectId, project.id));

        return {
          ...project,
          workItems,
          datasets,
        };
      })
    );
  }
}
