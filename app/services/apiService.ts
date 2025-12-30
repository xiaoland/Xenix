/**
 * API Service Layer
 * Encapsulates all API communication
 */

import type { Dataset, TaskInfo, TuningResult } from "~/types";

export class ApiService {
  /**
   * Dataset Management
   */
  static async registerDataset(file: File, name: string, description: string): Promise<{ success: boolean; dataset: Dataset }> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("name", name);
    formData.append("description", description);

    return await $fetch("/api/data", {
      method: "POST",
      body: formData,
    });
  }

  static async fetchDatasets(): Promise<{ success: boolean; datasets: Dataset[] }> {
    return await $fetch("/api/data");
  }

  /**
   * Model Training and Tuning
   */
  static async startAutoTune(params: {
    datasetId: string;
    features: string[];
    target: string;
    model: string;
    paramGrid?: Record<string, any>;
  }): Promise<{ success: boolean; taskId: number }> {
    return await $fetch("/api/auto-tune", {
      method: "POST",
      body: params,
    });
  }

  static async startManualTrain(params: {
    datasetId: string;
    features: string[];
    target: string;
    model: string;
    parameters: Record<string, any>;
  }): Promise<{ success: boolean; taskId: number }> {
    return await $fetch("/api/manual-tune", {
      method: "POST",
      body: params,
    });
  }

  /**
   * Task Management
   */
  static async fetchTaskStatus(taskId: number): Promise<{ task: TaskInfo }> {
    return await $fetch(`/api/task/${taskId}`);
  }

  static async fetchTaskLogs(taskId: number): Promise<{ success: boolean; logs: TaskLog[] }> {
    return await $fetch(`/api/obsrv/${taskId}`);
  }

  static async fetchTaskResults(taskId: number): Promise<{ success: boolean; results: TuningResult }> {
    return await $fetch(`/api/results/${taskId}`);
  }

  static async fetchTrainingHistory(model: string): Promise<{ success: boolean; results: TuningResult[] }> {
    return await $fetch(`/api/results/history/${model}`);
  }

  /**
   * Prediction
   */
  static async startPrediction(params: {
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

  /**
   * Model Metadata
   */
  static async fetchModelMetadata(): Promise<{ success: boolean; models: any[] }> {
    return await $fetch("/api/models");
  }
}
