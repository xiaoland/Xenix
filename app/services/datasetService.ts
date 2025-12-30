/**
 * Dataset Service
 * Handles dataset management operations
 */

import type { Dataset } from "~/types";

export class DatasetService {
  /**
   * Register a new dataset
   */
  static async register(
    file: File,
    name: string,
    description: string
  ): Promise<{ success: boolean; dataset: Dataset }> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("name", name);
    formData.append("description", description);

    return await $fetch("/api/data", {
      method: "POST",
      body: formData,
    });
  }

  /**
   * Fetch all datasets
   */
  static async fetchAll(): Promise<{ success: boolean; datasets: Dataset[] }> {
    return await $fetch("/api/data");
  }

  /**
   * Fetch a specific dataset by ID
   */
  static async fetchById(
    id: number | string
  ): Promise<{ success: boolean; dataset: Dataset }> {
    return await $fetch(`/api/data/${id}`);
  }
}
