/**
 * Task Repository
 * Handles database operations for tasks
 */
import { and, eq, inArray, sql } from 'drizzle-orm';

import { db, schema } from '../database/index.js';
import { BaseRepository } from './BaseRepository.js';

type Task = typeof schema.tasks.$inferSelect;

export class TaskRepository extends BaseRepository<Task> {
  constructor() {
    super(schema.tasks);
  }

  async findByWorkItem(workItemId: number, types?: string[]) {
    const conditions: any[] = [eq(schema.tasks.workItemId, workItemId)];

    if (types && types.length > 0) {
      conditions.push(inArray(schema.tasks.type, types));
    }

    return await db
      .select()
      .from(schema.tasks)
      .where(and(...conditions));
  }

  async updateStatus(id: number, status: string, result?: any, error?: string) {
    const updates: any = {
      status,
      endAt: new Date(),
    };

    if (result) updates.result = result;
    if (error) updates.error = error;

    return await this.update(id, updates);
  }

  async markAsRunning(id: number) {
    return await this.update(id, {
      status: 'running',
      startedAt: new Date(),
    });
  }

  async deleteFailedByWorkItem(workItemId: number) {
    return await db
      .delete(schema.tasks)
      .where(
        and(
          eq(schema.tasks.workItemId, workItemId),
          eq(schema.tasks.status, 'failed')
        )
      );
  }

  async deleteByModel(workItemId: number, model: string) {
    return await db
      .delete(schema.tasks)
      .where(
        and(
          eq(schema.tasks.workItemId, workItemId),
          sql`${schema.tasks.parameter} ->> 'model' = ${model}`
        )
      );
  }
}
