/**
 * Dataset Service
 * Handles dataset management operations
 */

import type { Dataset } from '@xenix/shared';
import { useAuthStore } from '../stores/auth';

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

    return await useAuthStore().requestWithToken("/api/data", {
      method: "POST",
      body: formData,
    });
  }

  /**
   * Fetch all datasets
   */
  static async fetchAll(): Promise<{ success: boolean; datasets: Dataset[] }> {
    return await useAuthStore().requestWithToken("/api/data");
  }

  /**
   * Fetch a specific dataset by ID
   */
  static async fetchById(
    id: number | string
  ): Promise<{ success: boolean; dataset: Dataset }> {
    return await useAuthStore().requestWithToken(`/api/data/${id}`);
  }
}
