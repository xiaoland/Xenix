/**
 * Prediction Service
 * Handles prediction operations
 */

import { useAuthStore } from '../stores/auth';

export class PredictionService {
  /**
   * Start prediction on new data from file
   * Backend fetches trainingDatasetId, featureColumns, targetColumn from workItemId
   */
  static async start(params: {
    file: File;
    model: string;
    tuningTaskId: number;
    workItemId: number;
  }): Promise<{ success: boolean; taskId: number; outputFile?: string }> {
    const formData = new FormData();
    formData.append("file", params.file);
    formData.append("model", params.model);
    formData.append("tuningTaskId", params.tuningTaskId.toString());
    formData.append("workItemId", params.workItemId.toString());

    return await useAuthStore().requestWithToken("/api/predict/by-file", {
      method: "POST",
      body: formData,
    });
  }

  /**
   * Start prediction with inline data
   * Backend fetches trainingDatasetId, featureColumns, targetColumn from workItemId
   */
  static async predictInline(params: {
    predictionData: Record<string, any>[];
    model: string;
    tuningTaskId: number;
    workItemId: number;
  }): Promise<{ success: boolean; taskId: number }> {
    return await useAuthStore().requestWithToken("/api/predict/inline", {
      method: "POST",
      body: {
        predictionData: params.predictionData,
        model: params.model,
        tuningTaskId: params.tuningTaskId,
        workItemId: params.workItemId,
      },
    });
  }
}
