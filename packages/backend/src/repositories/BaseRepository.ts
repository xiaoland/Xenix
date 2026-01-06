/**
 * Base Repository
 * Provides common database operations
 */
import { eq } from 'drizzle-orm';

import { db } from '../database/index.js';

export abstract class BaseRepository<T> {
  constructor(protected table: any) {}

  async findAll(): Promise<T[]> {
    return await db.select().from(this.table);
  }

  async findById(id: number): Promise<T | null> {
    const results = await db
      .select()
      .from(this.table)
      .where(eq(this.table.id, id))
      .limit(1);
    return results[0] || null;
  }

  async create(data: any): Promise<T> {
    const results: any = await db.insert(this.table).values(data).returning();
    return results[0];
  }

  async update(id: number, data: any): Promise<T | null> {
    const results: any = await db
      .update(this.table)
      .set(data)
      .where(eq(this.table.id, id))
      .returning();
    return results[0] || null;
  }

  async delete(id: number): Promise<void> {
    await db.delete(this.table).where(eq(this.table.id, id));
  }
}
