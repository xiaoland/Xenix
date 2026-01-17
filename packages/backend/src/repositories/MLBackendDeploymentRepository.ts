/**
 * Repository for ML Backend Deployments
 * Handles CRUD operations for ml_backend_deployments table
 */

import { eq, and } from 'drizzle-orm';
import { db } from '../database';
import { mlBackendDeployments } from '../database/schema';
import type {
  MLBackendDeployment,
  CreateMLBackendDeploymentDTO,
  UpdateMLBackendDeploymentDTO,
} from '../types/ml-backend';

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
   * Find the default deployment
   */
  async findDefaultDeployment(): Promise<MLBackendDeployment | null> {
    const result = await db
      .select()
      .from(mlBackendDeployments)
      .where(
        and(
          eq(mlBackendDeployments.isDefault, true),
          eq(mlBackendDeployments.isActive, true),
        ),
      )
      .limit(1);

    return result[0] || null;
  }

  /**
   * Find all deployments by type
   */
  async findByType(
    deploymentType: 'http' | 'http-proxy-frontend',
    activeOnly: boolean = true,
  ): Promise<MLBackendDeployment[]> {
    const conditions = [eq(mlBackendDeployments.deploymentType, deploymentType)];

    if (activeOnly) {
      conditions.push(eq(mlBackendDeployments.isActive, true));
    }

    const result = await db
      .select()
      .from(mlBackendDeployments)
      .where(and(...conditions));

    return result;
  }

  /**
   * Find all active deployments
   */
  async findAllActive(): Promise<MLBackendDeployment[]> {
    const result = await db
      .select()
      .from(mlBackendDeployments)
      .where(eq(mlBackendDeployments.isActive, true));

    return result;
  }

  /**
   * Create a new deployment
   */
  async create(data: CreateMLBackendDeploymentDTO): Promise<MLBackendDeployment> {
    const result = await db
      .insert(mlBackendDeployments)
      .values({
        name: data.name,
        createdBy: data.created_by || null,
        deploymentType: data.deployment_type,
        deploymentParams: data.deployment_params as any,
        isDefault: data.is_default || false,
        isActive: data.is_active !== undefined ? data.is_active : true,
      })
      .returning();

    return result[0];
  }

  /**
   * Update an existing deployment
   */
  async update(
    id: number,
    data: UpdateMLBackendDeploymentDTO,
  ): Promise<MLBackendDeployment | null> {
    const updateData: any = {
      updatedAt: new Date(),
    };

    if (data.name !== undefined) updateData.name = data.name;
    if (data.deployment_params !== undefined)
      updateData.deploymentParams = data.deployment_params;
    if (data.is_default !== undefined) updateData.isDefault = data.is_default;
    if (data.is_active !== undefined) updateData.isActive = data.is_active;

    const result = await db
      .update(mlBackendDeployments)
      .set(updateData)
      .where(eq(mlBackendDeployments.id, id))
      .returning();

    return result[0] || null;
  }

  /**
   * Delete a deployment (soft delete by setting is_active = false)
   */
  async softDelete(id: number): Promise<boolean> {
    const result = await db
      .update(mlBackendDeployments)
      .set({
        isActive: false,
        updatedAt: new Date(),
      })
      .where(eq(mlBackendDeployments.id, id))
      .returning();

    return result.length > 0;
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

  /**
   * Set a deployment as the default deployment
   * This will unset all other deployments as default
   */
  async setAsDefault(id: number): Promise<MLBackendDeployment | null> {
    // First, unset all other deployments as default
    await db
      .update(mlBackendDeployments)
      .set({ isDefault: false, updatedAt: new Date() })
      .where(eq(mlBackendDeployments.isDefault, true));

    // Then set the target deployment as default
    const result = await db
      .update(mlBackendDeployments)
      .set({ isDefault: true, updatedAt: new Date() })
      .where(eq(mlBackendDeployments.id, id))
      .returning();

    return result[0] || null;
  }
}
