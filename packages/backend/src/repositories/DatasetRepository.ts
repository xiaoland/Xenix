/**
 * Dataset Repository
 * Handles database operations for datasets
 */
import { desc } from "drizzle-orm";

import { db, schema } from "../database";
import { BaseRepository } from "./BaseRepository";

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
