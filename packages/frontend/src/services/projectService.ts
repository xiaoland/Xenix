/**
 * Project Service
 * Handles project management operations
 */

import type { Project } from '@xenix/shared';
import { useAuthStore } from '../stores/auth';

export class ProjectService {
  /**
   * Fetch all projects
   */
  static async fetchAll(): Promise<{ success: boolean; projects: Project[] }> {
    return await useAuthStore().requestWithToken('/api/projects');
  }

  /**
   * Fetch a specific project by ID (with optional nested data)
   */
  static async fetchById(
    id: number | string
  ): Promise<{ success: boolean; project: Project }> {
    return await useAuthStore().requestWithToken(`/api/projects/${id}`);
  }

  /**
   * Create a new project
   */
  static async create(project: {
    name: string;
    description?: string;
  }): Promise<{ success: boolean; project: Project }> {
    return await useAuthStore().requestWithToken('/api/projects', {
      method: 'POST',
      body: JSON.stringify(project),
    });
  }

  /**
   * Update a project
   */
  static async update(
    id: number | string,
    updates: {
      name?: string;
      description?: string;
      status?: 'active' | 'completed' | 'archived';
    }
  ): Promise<{ success: boolean; project: Project }> {
    return await useAuthStore().requestWithToken(`/api/projects/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  /**
   * Delete a project
   */
  static async delete(id: number | string): Promise<{ success: boolean }> {
    return await useAuthStore().requestWithToken(`/api/projects/${id}`, {
      method: 'DELETE',
    });
  }
}
