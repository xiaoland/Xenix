/**
 * Model Service
 * Handles model metadata operations
 */

export class ModelService {
  /**
   * Fetch model metadata and schemas
   */
  static async fetchMetadata(): Promise<{ success: boolean; models: any[] }> {
    return await $fetch("/api/models");
  }
}
