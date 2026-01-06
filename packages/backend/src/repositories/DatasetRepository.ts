/**
 * Dataset Repository
 * Handles database operations for datasets
 */

import { BaseRepository } from './BaseRepository.js';
import { db, schema } from '../database/index.js';
import { desc } from 'drizzle-orm';

type Dataset = typeof schema.datasets.$inferSelect;

export class DatasetRepository extends BaseRepository<Dataset> {
  constructor() {
    super(schema.datasets);
  }

  async findAll() {
    return await db
      .select()
      .from(schema.datasets)
      .orderBy(desc(schema.datasets.createdAt));
  }
}
