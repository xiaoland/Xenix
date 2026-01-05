/**
 * Task Service
 * Handles task status and logs operations
 */

import type { TaskInfo, TaskLog } from "~/types";
import { useAuthStore } from "~/stores/auth";

export class TaskService {
  /**
   * Fetch task status and details
   */
  static async fetchStatus(taskId: number): Promise<{ task: TaskInfo }> {
    return await useAuthStore().requestWithToken(`/api/task/${taskId}`);
  }

  /**
   * Fetch task logs
   */
  static async fetchLogs(
    taskId: number
  ): Promise<{ success: boolean; logs: TaskLog[] }> {
    return await useAuthStore().requestWithToken(`/api/obsrv/${taskId}`);
  }

  /**
   * Delete all failed tasks for a work item
   */
  static async deleteFailedTasks(
    workItemId: number
  ): Promise<{ success: boolean; message: string }> {
    return await useAuthStore().requestWithToken(
      `/api/tasks/failed?workItemId=${workItemId}`,
      {
        method: "DELETE",
      }
    );
  }

  /**
   * Delete all tasks for a specific model in a work item
   */
  static async deleteByModel(
    workItemId: number,
    model: string
  ): Promise<{ success: boolean; message: string }> {
    return await useAuthStore().requestWithToken(
      `/api/tasks/model?workItemId=${workItemId}&model=${encodeURIComponent(
        model
      )}`,
      {
        method: "DELETE",
      }
    );
  }

  /**
   * Fetch tasks for a work item
   */
  static async fetchByWorkItemId(
    workItemId: number,
    types?: string[]
  ): Promise<{ success: boolean; tasks: TaskInfo[] }> {
    const queryParams = new URLSearchParams({
      workItemId: workItemId.toString(),
    });
    if (types && types.length > 0) {
      queryParams.append("type", types.join(","));
    }
    return await useAuthStore().requestWithToken(
      `/api/tasks?${queryParams.toString()}`
    );
  }
}
