/**
 * Project Service
 * Handles project management operations
 */

import type { Project } from "~/types";

export class ProjectService {
  /**
   * Fetch all projects
   */
  static async fetchAll(): Promise<{ success: boolean; projects: Project[] }> {
    return await $fetch("/api/projects");
  }

  /**
   * Fetch a specific project by ID (with optional nested data)
   */
  static async fetchById(id: number | string): Promise<{ success: boolean; project: Project }> {
    return await $fetch(`/api/projects/${id}`);
  }

  /**
   * Create a new project
   */
  static async create(project: {
    name: string;
    description?: string;
  }): Promise<{ success: boolean; project: Project }> {
    return await $fetch("/api/projects", {
      method: "POST",
      body: project,
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
      status?: "active" | "completed" | "archived";
    }
  ): Promise<{ success: boolean; project: Project }> {
    return await $fetch(`/api/projects/${id}`, {
      method: "PUT",
      body: updates,
    });
  }

  /**
   * Delete a project
   */
  static async delete(id: number | string): Promise<{ success: boolean }> {
    return await $fetch(`/api/projects/${id}`, {
      method: "DELETE",
    });
  }
}
