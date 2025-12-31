/**
 * Prediction Service
 * Handles prediction operations
 */

export class PredictionService {
  /**
   * Start prediction on new data
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

    return await $fetch("/api/predict", {
      method: "POST",
      body: formData,
    });
  }
}
