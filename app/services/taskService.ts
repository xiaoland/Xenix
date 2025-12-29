/**
 * Task Service
 * Handles task status, logs, and results operations
 */

import type { TaskInfo, TaskLog, TuningResult } from "~/types";

export class TaskService {
  /**
   * Fetch task status
   */
  static async fetchStatus(taskId: number): Promise<{ task: TaskInfo }> {
    return await $fetch(`/api/task/${taskId}`);
  }

  /**
   * Fetch task logs
   */
  static async fetchLogs(taskId: number): Promise<{ success: boolean; logs: TaskLog[] }> {
    return await $fetch(`/api/obsrv/${taskId}`);
  }

  /**
   * Fetch task results
   */
  static async fetchResults(taskId: number): Promise<{ success: boolean; results: TuningResult }> {
    return await $fetch(`/api/results/${taskId}`);
  }

  /**
   * Fetch training history for a specific model
   */
  static async fetchTrainingHistory(model: string): Promise<{ success: boolean; results: TuningResult[] }> {
    return await $fetch(`/api/results/history/${model}`);
  }
}
