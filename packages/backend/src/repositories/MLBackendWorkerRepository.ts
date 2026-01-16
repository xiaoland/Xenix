/**
 * Repository for ML Backend Workers
 * Handles CRUD operations for ml_backend_workers table
 */

import { eq, and } from 'drizzle-orm';
import { db } from '../database';
import { mlBackendWorkers } from '../database/schema';
import type {
  MLBackendWorker,
  CreateMLBackendWorkerDTO,
  UpdateMLBackendWorkerDTO,
} from '../types/ml-backend';

export class MLBackendWorkerRepository {
  /**
   * Find a worker by ID
   */
  async findById(id: number): Promise<MLBackendWorker | null> {
    const result = await db
      .select()
      .from(mlBackendWorkers)
      .where(eq(mlBackendWorkers.id, id))
      .limit(1);

    return result[0] || null;
  }

  /**
   * Find the default worker
   */
  async findDefaultWorker(): Promise<MLBackendWorker | null> {
    const result = await db
      .select()
      .from(mlBackendWorkers)
      .where(
        and(
          eq(mlBackendWorkers.isDefault, true),
          eq(mlBackendWorkers.isActive, true),
        ),
      )
      .limit(1);

    return result[0] || null;
  }

  /**
   * Find all workers by adapter type
   */
  async findByAdapter(
    adapter: 'aliyun-fc' | 'spawn',
    activeOnly: boolean = true,
  ): Promise<MLBackendWorker[]> {
    const conditions = [eq(mlBackendWorkers.adapter, adapter)];

    if (activeOnly) {
      conditions.push(eq(mlBackendWorkers.isActive, true));
    }

    const result = await db
      .select()
      .from(mlBackendWorkers)
      .where(and(...conditions));

    return result;
  }

  /**
   * Find all active workers
   */
  async findAllActive(): Promise<MLBackendWorker[]> {
    const result = await db
      .select()
      .from(mlBackendWorkers)
      .where(eq(mlBackendWorkers.isActive, true));

    return result;
  }

  /**
   * Create a new worker
   */
  async create(data: CreateMLBackendWorkerDTO): Promise<MLBackendWorker> {
    const result = await db
      .insert(mlBackendWorkers)
      .values({
        name: data.name,
        createdBy: data.created_by || null,
        adapter: data.adapter,
        adapterParams: data.adapter_params as any,
        isDefault: data.is_default || false,
        isActive: data.is_active !== undefined ? data.is_active : true,
      })
      .returning();

    return result[0];
  }

  /**
   * Update an existing worker
   */
  async update(
    id: number,
    data: UpdateMLBackendWorkerDTO,
  ): Promise<MLBackendWorker | null> {
    const updateData: any = {
      updatedAt: new Date(),
    };

    if (data.name !== undefined) updateData.name = data.name;
    if (data.adapter_params !== undefined)
      updateData.adapterParams = data.adapter_params;
    if (data.is_default !== undefined) updateData.isDefault = data.is_default;
    if (data.is_active !== undefined) updateData.isActive = data.is_active;

    const result = await db
      .update(mlBackendWorkers)
      .set(updateData)
      .where(eq(mlBackendWorkers.id, id))
      .returning();

    return result[0] || null;
  }

  /**
   * Delete a worker (soft delete by setting is_active = false)
   */
  async softDelete(id: number): Promise<boolean> {
    const result = await db
      .update(mlBackendWorkers)
      .set({
        isActive: false,
        updatedAt: new Date(),
      })
      .where(eq(mlBackendWorkers.id, id))
      .returning();

    return result.length > 0;
  }

  /**
   * Hard delete a worker
   */
  async delete(id: number): Promise<boolean> {
    const result = await db
      .delete(mlBackendWorkers)
      .where(eq(mlBackendWorkers.id, id))
      .returning();

    return result.length > 0;
  }

  /**
   * Set a worker as the default worker
   * This will unset all other workers as default
   */
  async setAsDefault(id: number): Promise<MLBackendWorker | null> {
    // First, unset all other workers as default
    await db
      .update(mlBackendWorkers)
      .set({ isDefault: false, updatedAt: new Date() })
      .where(eq(mlBackendWorkers.isDefault, true));

    // Then set the target worker as default
    const result = await db
      .update(mlBackendWorkers)
      .set({ isDefault: true, updatedAt: new Date() })
      .where(eq(mlBackendWorkers.id, id))
      .returning();

    return result[0] || null;
  }
}
