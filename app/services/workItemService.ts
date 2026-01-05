/**
 * WorkItem Service
 * Handles work item management operations
 */

import type { WorkItem } from "~/types";

import { useAuthStore } from "~/stores/auth";

export class WorkItemService {
  /**
   * Fetch all work items
   */
  static async fetchAll(): Promise<{
    success: boolean;
    workItems: WorkItem[];
  }> {
    return await useAuthStore().requestWithToken("/api/work-items");
  }

  /**
   * Fetch a specific work item by ID
   */
  static async fetchById(
    id: number | string
  ): Promise<{ success: boolean; workItem: WorkItem }> {
    return await useAuthStore().requestWithToken(`/api/work-items/${id}`);
  }

  /**
   * Create a new work item
   */
  static async create(workItem: {
    projectId: number;
    name: string;
    description?: string;
  }): Promise<{ success: boolean; workItem: WorkItem }> {
    return await useAuthStore().requestWithToken("/api/work-items", {
      method: "POST",
      body: workItem,
    });
  }

  /**
   * Update a work item
   */
  static async update(
    id: number | string,
    updates: {
      name?: string;
      description?: string;
      status?: "active" | "completed" | "archived";
      datasetId?: number;
      featureColumns?: string[];
      targetColumn?: string;
      selectedModels?: string[];
    }
  ): Promise<{ success: boolean; workItem: WorkItem }> {
    return await useAuthStore().requestWithToken(`/api/work-items/${id}`, {
      method: "PUT",
      body: updates,
    });
  }

  /**
   * Delete a work item
   */
  static async delete(id: number | string): Promise<{ success: boolean }> {
    return await useAuthStore().requestWithToken(`/api/work-items/${id}`, {
      method: "DELETE",
    });
  }
}
