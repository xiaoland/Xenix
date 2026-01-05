/**
 * Model Service
 * Handles model metadata operations
 */

import { useAuthStore } from '../stores/auth';

export class ModelService {
  /**
   * Fetch model metadata and schemas
   */
  static async fetchMetadata(): Promise<{ success: boolean; models: any[] }> {
    return await useAuthStore().requestWithToken("/api/models");
  }

  /**
   * Fetch a single model metadata by name
   */
  static async fetchModel(
    name: string
  ): Promise<{ success: boolean; model: any }> {
    return await useAuthStore().requestWithToken(`/api/models/${name}`);
  }
}
