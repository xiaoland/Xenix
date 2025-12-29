/**
 * Composable for managing ModelTuningTable data fetching and state
 * Handles fetching tuning results, task logs, training history, and status
 */

import { ref, computed, watch, toRef } from "vue";
import { useI18n } from "vue-i18n";
import { WorkItemService, TaskService } from "~/services";
import type { TuningResult } from "~/types";

export function useModelTuningTableData(workItemId: any) {
  const workItemIdRef = toRef(workItemId);
  const { t } = useI18n();

  // Data states
  const availableModels = ref<Array<{ label: string; value: string }>>([]);
  const tuningStatus = ref<Record<string, string>>({});
  const tuningTasks = ref<Record<string, number>>({});
  const tuningResults = ref<TuningResult[]>([]);
  const taskLogs = ref<Record<string, any[]>>({});
  const trainingHistory = ref<Record<string, any[]>>({});
  const isTuning = ref(false);

  // UI states
  const expandedKeys = ref<string[]>([]);

  /**
   * Fetch tuning data for work item
   */
  const fetchTuningData = async () => {
    if (!workItemIdRef.value) return;

    try {
      const response = await WorkItemService.fetchById(workItemIdRef.value);
      if (response.success && response.workItem) {
        const workItem = response.workItem;

        // Extract available models from tasks or use defaults
        const models = new Set<string>();
        if (workItem.tasks) {
          workItem.tasks.forEach((task: any) => {
            if (task.parameter?.model) {
              models.add(task.parameter.model);
            }
          });
        }

        // Build available models list (use i18n translation if available)
        const modelsList = Array.from(models).map((model) => {
          const translated = t(`models.${model.split(".").pop()}`);
          const base = model.split(".").pop() || model;
          const label =
            translated === model ? base.replace(/_/g, " ") : translated;
          return { label, value: model };
        });
        availableModels.value = modelsList;

        // Process tasks and build status, tuningTasks, and results
        const statusMap: Record<string, string> = {};
        const tasksMap: Record<string, number> = {};
        const resultsMap: TuningResult[] = [];

        if (workItem.tasks) {
          for (const task of workItem.tasks as any[]) {
            const model = task.parameter?.model;
            if (!model) continue;

            statusMap[model] = task.status || "pending";
            if (task.id) {
              tasksMap[model] = task.id;
            }

            // Collect completed tuning results
            if (task.type === "auto-tune" && task.status === "completed") {
              resultsMap.push({
                model: model,
                params: task.result?.params || {},
                metrics: {
                  mse_train: task.result?.mse_train,
                  mae_train: task.result?.mae_train,
                  r2_train: task.result?.r2_train,
                  mse_test: task.result?.mse_test,
                  mae_test: task.result?.mae_test,
                  r2_test: task.result?.r2_test,
                },
                status: task.status,
                trainingType: task.parameter?.trainingType || "auto-tune",
                createdAt: task.createdAt,
                taskId: task.id,
              } as any);
            }
          }
        }

        tuningStatus.value = statusMap;
        tuningTasks.value = tasksMap;
        tuningResults.value = resultsMap;

        // Determine if tuning is in progress
        isTuning.value = Object.values(statusMap).some(
          (status) => status === "processing" || status === "pending"
        );

        // Fetch training history for each model
        for (const model of modelsList) {
          await fetchTrainingHistory(model.value);
        }
      }
    } catch (error) {
      console.error("Failed to fetch tuning data:", error);
    }
  };

  /**
   * Fetch training history for a specific model
   */
  const fetchTrainingHistory = async (model: string) => {
    try {
      const response = await TaskService.fetchTrainingHistory(model);
      if (response.success && response.results) {
        trainingHistory.value[model] = response.results;
      }
    } catch (error) {
      console.error(`Failed to fetch training history for ${model}:`, error);
    }
  };

  /**
   * Fetch logs for a specific task
   */
  const fetchTaskLogs = async (taskId: number) => {
    try {
      const response = await TaskService.fetchLogs(taskId);
      if (response.success && response.logs) {
        taskLogs.value[taskId] = response.logs;
      }
    } catch (error) {
      console.error(`Failed to fetch logs for task ${taskId}:`, error);
    }
  };

  /**
   * Handle row expansion
   */
  const handleExpand = (expanded: boolean, record: any) => {
    if (expanded) {
      if (!expandedKeys.value.includes(record.model)) {
        expandedKeys.value.push(record.model);
      }
      fetchTrainingHistory(record.model);
    } else {
      expandedKeys.value = expandedKeys.value.filter(
        (key) => key !== record.model
      );
    }
  };

  /**
   * Combine all data sources into a single table data structure
   */
  const tableData = computed(() => {
    const data: any[] = [];

    for (const model of availableModels.value) {
      const status = tuningStatus.value[model.value];
      const taskId = tuningTasks.value[model.value];
      const result = tuningResults.value.find(
        (r: any) => r.model === model.value
      );

      // Build children array for expandable rows
      const children: any[] = [];

      // Add historical tasks
      const history = trainingHistory.value[model.value] || [];
      for (const historyItem of history) {
        children.push({
          model: model.value,
          label: model.label,
          taskId: historyItem.taskId,
          status: historyItem.status || "completed",
          metrics: {
            r2_test: historyItem.r2_test,
            mse_test: historyItem.mse_test,
            mae_test: historyItem.mae_test,
          },
          params: historyItem.params,
          trainingType: historyItem.trainingType,
          createdAt: historyItem.createdAt,
          isHistory: true,
        });
      }

      // Add current active task if not in history
      if (status && taskId) {
        const existsInHistory = history.some((h: any) => h.taskId === taskId);
        if (!existsInHistory) {
          children.push({
            model: model.value,
            label: model.label,
            taskId: taskId,
            status: status,
            metrics: result
              ? {
                  r2_test: result.metrics?.r2_test,
                  mse_test: result.metrics?.mse_test,
                  mae_test: result.metrics?.mae_test,
                }
              : null,
            params: result?.params,
            trainingType: result?.trainingType || "auto",
            createdAt: result?.createdAt || new Date(),
            isHistory: true,
            isCurrent: true,
          });
        }
      }

      // Parent row
      const parentRow = {
        model: model.value,
        label: model.label,
        children: children,
        isHistory: false,
      };

      data.push(parentRow);
    }

    return data;
  });

  /**
   * Get row key for table
   */
  const getRowKey = (record: any) => {
    return record.isHistory ? `${record.model}-${record.taskId}` : record.model;
  };

  // Watch for workItemId changes and refetch data
  watch(
    workItemIdRef,
    () => {
      if (workItemIdRef.value) {
        fetchTuningData();
      }
    },
    { immediate: true }
  );

  return {
    availableModels,
    tuningStatus,
    tuningTasks,
    tuningResults,
    taskLogs,
    trainingHistory,
    isTuning,
    expandedKeys,
    tableData,
    getRowKey,
    handleExpand,
    fetchTaskLogs,
  };
}
