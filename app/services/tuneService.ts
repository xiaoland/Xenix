/**
 * Tune Service
 * Handles all model tuning operations (auto-tune and manual-tune)
 */

export class TuneService {
  /**
   * Start auto-tune with hyperparameter grid search
   */
  static async startAutoTune(params: {
    datasetId: string;
    features: string[];
    target: string;
    model: string;
    paramGrid?: Record<string, any>;
    workItemId?: number;
  }): Promise<{ success: boolean; taskId: number }> {
    return await $fetch("/api/auto-tune", {
      method: "POST",
      body: params,
    });
  }

  /**
   * Start manual tune with specific parameters
   */
  static async startManualTune(params: {
    datasetId: string;
    features: string[];
    target: string;
    model: string;
    parameters: Record<string, any>;
    workItemId?: number;
  }): Promise<{ success: boolean; taskId: number }> {
    return await $fetch("/api/manual-tune", {
      method: "POST",
      body: params,
    });
  }
}
