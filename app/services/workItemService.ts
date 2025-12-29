/**
 * WorkItem Service
 * Handles work item management operations
 */

import type { WorkItem } from "~/types";

export class WorkItemService {
  /**
   * Fetch all work items
   */
  static async fetchAll(): Promise<{ success: boolean; workItems: WorkItem[] }> {
    return await $fetch("/api/work-items");
  }

  /**
   * Fetch a specific work item by ID
   */
  static async fetchById(id: number | string): Promise<{ success: boolean; workItem: WorkItem }> {
    return await $fetch(`/api/work-items/${id}`);
  }

  /**
   * Create a new work item
   */
  static async create(workItem: {
    projectId: number;
    name: string;
    description?: string;
  }): Promise<{ success: boolean; workItem: WorkItem }> {
    return await $fetch("/api/work-items", {
      method: "POST",
      body: workItem,
    });
  }

  /**
   * Update a work item
   */
  static async update(
    id: number,
    updates: {
      name?: string;
      description?: string;
      status?: "active" | "completed" | "archived";
      datasetId?: number;
      featureColumns?: string[];
      targetColumn?: string;
    }
  ): Promise<{ success: boolean; workItem: WorkItem }> {
    return await $fetch(`/api/work-items/${id}`, {
      method: "PUT",
      body: updates,
    });
  }

  /**
   * Delete a work item
   */
  static async delete(id: number): Promise<{ success: boolean }> {
    return await $fetch(`/api/work-items/${id}`, {
      method: "DELETE",
    });
  }
}
