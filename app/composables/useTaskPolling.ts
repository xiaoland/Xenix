/**
 * Composable for managing task polling and status tracking
 */

import { ref } from "vue";
import { ApiService } from "~/services/apiService";
import type { TaskStatus } from "~/types";

export function useTaskPolling() {
  const tuningStatus = ref<Record<string, TaskStatus>>({});
  const tuningTasks = ref<Record<string, number>>({});
  const taskLogs = ref<Record<string, any[]>>({});

  /**
   * Fetch logs for a specific task
   */
  const fetchTaskLogs = async (taskId: number) => {
    try {
      const response = await ApiService.fetchTaskLogs(taskId);
      if (response.success) {
        taskLogs.value[taskId] = response.logs.reverse();
      }
    } catch (error) {
      console.error(`Failed to fetch logs for ${taskId}:`, error);
    }
  };

  /**
   * Poll task logs with intervals
   */
  const pollTaskLogs = (taskId: number) => {
    fetchTaskLogs(taskId);

    const interval = setInterval(async () => {
      await fetchTaskLogs(taskId);

      const isComplete = Object.values(tuningStatus.value).every(
        (status) => status === "completed" || status === "failed"
      );
      if (isComplete) {
        clearInterval(interval);
      }
    }, 3000);
  };

  /**
   * Poll task status until completion
   */
  const pollTaskStatus = async (
    taskId: number,
    modelValue?: string,
    maxAttempts: number = 120
  ) => {
    let attempts = 0;

    while (attempts < maxAttempts) {
      try {
        const response = await ApiService.fetchTaskStatus(taskId);

        if (
          modelValue &&
          response.task.status !== tuningStatus.value[modelValue]
        ) {
          tuningStatus.value[modelValue] = response.task.status as TaskStatus;
        }

        if (response.task.status === "completed" || response.task.status === "failed") {
          return response;
        }

        attempts++;
        if (attempts < maxAttempts) {
          await new Promise((resolve) => setTimeout(resolve, 5000));
        }
      } catch (error) {
        console.error("Failed to poll task status:", error);
        attempts++;
        if (attempts < maxAttempts) {
          await new Promise((resolve) => setTimeout(resolve, 5000));
        }
      }
    }

    return null;
  };

  /**
   * Register a new task for tracking
   */
  const registerTask = (modelValue: string, taskId: number, status: TaskStatus = "running") => {
    tuningTasks.value[modelValue] = taskId;
    tuningStatus.value[modelValue] = status;
  };

  /**
   * Clear all task tracking
   */
  const clearTasks = () => {
    tuningStatus.value = {};
    tuningTasks.value = {};
    taskLogs.value = {};
  };

  return {
    tuningStatus,
    tuningTasks,
    taskLogs,
    fetchTaskLogs,
    pollTaskLogs,
    pollTaskStatus,
    registerTask,
    clearTasks,
  };
}
