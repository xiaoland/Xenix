/**
 * Training Service
 * Handles model training and tuning operations
 */

export class TrainingService {
  /**
   * Start auto-tune with hyperparameter grid search
   */
  static async startAutoTune(params: {
    datasetId: string;
    features: string[];
    target: string;
    model: string;
    paramGrid?: Record<string, any>;
  }): Promise<{ success: boolean; taskId: number }> {
    return await $fetch("/api/tune", {
      method: "POST",
      body: params,
    });
  }

  /**
   * Start manual training with specific parameters
   */
  static async startManualTrain(params: {
    datasetId: string;
    features: string[];
    target: string;
    model: string;
    parameters: Record<string, any>;
  }): Promise<{ success: boolean; taskId: number }> {
    return await $fetch("/api/train", {
      method: "POST",
      body: params,
    });
  }
}
