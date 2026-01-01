/**
 * Task Service
 * Handles task status and logs operations
 */

import type { TaskInfo, TaskLog } from "~/types";

export class TaskService {
  /**
   * Fetch task status and details
   */
  static async fetchStatus(taskId: number): Promise<{ task: TaskInfo }> {
    return await $fetch(`/api/task/${taskId}`);
  }

  /**
   * Fetch task logs
   */
  static async fetchLogs(
    taskId: number
  ): Promise<{ success: boolean; logs: TaskLog[] }> {
    return await $fetch(`/api/obsrv/${taskId}`);
  }

  /**
   * Delete all failed tasks for a work item
   */
  static async deleteFailedTasks(
    workItemId: number
  ): Promise<{ success: boolean; message: string }> {
    return await $fetch(`/api/tasks/failed?workItemId=${workItemId}`, {
      method: "DELETE",
    });
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
    return await $fetch(`/api/tasks?${queryParams.toString()}`);
  }
}
