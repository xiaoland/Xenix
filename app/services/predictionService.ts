/**
 * Prediction Service
 * Handles prediction operations
 */

export class PredictionService {
  /**
   * Start prediction on new data
   */
  static async start(params: {
    file: File;
    model: string;
    tuningTaskId: number;
    trainingDatasetId: string;
    featureColumns: string[];
    targetColumn: string;
  }): Promise<{ success: boolean; taskId: number; outputFile?: string }> {
    const formData = new FormData();
    formData.append("file", params.file);
    formData.append("model", params.model);
    formData.append("tuningTaskId", params.tuningTaskId.toString());
    formData.append("trainingDatasetId", params.trainingDatasetId);
    formData.append("featureColumns", JSON.stringify(params.featureColumns));
    formData.append("targetColumn", params.targetColumn);

    return await $fetch("/api/predict", {
      method: "POST",
      body: formData,
    });
  }
}
