/**
 * Repository for ML Backend Deployments
 * Handles CRUD operations for ml_backend_deployments table
 */

import { eq } from 'drizzle-orm';
import type { InferSelectModel, InferInsertModel } from 'drizzle-orm';
import { db } from '../database';
import { mlBackendDeployments } from '../database/schema';

type MLBackendDeployment = InferSelectModel<typeof mlBackendDeployments>;
type CreateMLBackendDeploymentDTO = InferInsertModel<typeof mlBackendDeployments>;

export class MLBackendDeploymentRepository {
  /**
   * Find a deployment by ID
   */
  async findById(id: number): Promise<MLBackendDeployment | null> {
    const result = await db
      .select()
      .from(mlBackendDeployments)
      .where(eq(mlBackendDeployments.id, id))
      .limit(1);

    return result[0] || null;
  }

  /**
   * Create a new deployment
   */
  async create(data: CreateMLBackendDeploymentDTO): Promise<MLBackendDeployment> {
    const result = await db
      .insert(mlBackendDeployments)
      .values({
        name: data.name,
        createdBy: data.createdBy || null,
        apiUrl: data.apiUrl,
        proxy: data.proxy || null,
        storage: data.storage || 'local',
      })
      .returning();

    return result[0];
  }

  /**
   * Update an existing deployment
   */
  async update(
    id: number,
    data: Partial<Omit<CreateMLBackendDeploymentDTO, 'id' | 'createdAt'>>,
  ): Promise<MLBackendDeployment | null> {
    const updateData: any = {};

    if (data.name !== undefined) updateData.name = data.name;
    if (data.apiUrl !== undefined) updateData.apiUrl = data.apiUrl;
    if (data.proxy !== undefined) updateData.proxy = data.proxy;
    if (data.storage !== undefined) updateData.storage = data.storage;

    const result = await db
      .update(mlBackendDeployments)
      .set(updateData)
      .where(eq(mlBackendDeployments.id, id))
      .returning();

    return result[0] || null;
  }

  /**
   * Hard delete a deployment
   */
  async delete(id: number): Promise<boolean> {
    const result = await db
      .delete(mlBackendDeployments)
      .where(eq(mlBackendDeployments.id, id))
      .returning();

    return result.length > 0;
  }
}
