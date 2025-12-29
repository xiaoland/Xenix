/**
 * Composable for managing tuning step logic
 * Handles model training, tuning results, and task management
 */

import { ref, type Ref } from "vue";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";
import { useModelTraining } from "./useModelTraining";
import { useTaskPolling } from "./useTaskPolling";
import { useDatasetRegistration } from "./useDatasetRegistration";
import { WorkItemService } from "~/services";
import type { TuningResult } from "~/types";

export function useTuningStep() {
  const { t } = useI18n();
  const { isTuning, executeTrain } = useModelTraining();
  const {
    tuningStatus,
    tuningTasks,
    taskLogs,
    pollTaskLogs,
    pollTaskStatus,
    registerTask,
    clearTasks,
  } = useTaskPolling();
  const { uploadedDatasetId, registerFileAsDataset } = useDatasetRegistration();

  // Local state
  const selectedModels = ref<string[]>([]);
  const activeLogTab = ref<string>("");
  const selectedBestModel = ref<string | null>(null);
  const selectedTaskId = ref<number | null>(null);
  const tuningResults = ref<TuningResult[]>([]);

  /**
   * Fetch existing tuning results for work item
   */
  const fetchTuningResults = async (workItemId?: number) => {
    if (!workItemId) return;

    try {
      const response = await WorkItemService.fetchById(workItemId);
      if (response.success && response.workItem.tasks) {
        const tasks = response.workItem.tasks.filter(
          (t: any) => t.type === "auto-tune" && t.status === "completed"
        );

        // Build tuning results from completed tasks
        tuningResults.value = tasks.map((task: any) => ({
          model: task.parameter?.model || "",
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
          trainingType: task.parameter?.trainingType || "auto",
          createdAt: task.createdAt,
          taskId: task.id,
        }));

        // Register tasks for polling
        tasks.forEach((task: any) => {
          if (task.parameter?.model) {
            registerTask(task.parameter.model, task.id, task.status);
          }
        });
      }
    } catch (error) {
      console.error("Failed to fetch tuning results:", error);
    }
  };

  /**
   * Get or register dataset ID
   */
  const getDatasetId = async (trainingFileList: any[]): Promise<string | null> => {
    let datasetIdToUse = uploadedDatasetId.value;

    if (!datasetIdToUse && trainingFileList.length > 0) {
      const file = trainingFileList[0].originFileObj;
      const registeredId = await registerFileAsDataset(file);
      if (registeredId) {
        datasetIdToUse = registeredId;
      }
    }

    if (!datasetIdToUse) {
      message.error(t("messages.datasetRegistrationFailed"));
      return null;
    }

    return datasetIdToUse;
  };

  /**
   * Start tuning all selected models
   */
  const startBatchTuning = async (params: {
    trainingFileList: any[];
    selectedFeatureColumns: string[];
    selectedTargetColumn: string;
    workItemId?: number;
  }) => {
    if (!uploadedDatasetId.value && params.trainingFileList.length === 0) {
      message.error(t("messages.uploadError"));
      return;
    }

    const datasetIdToUse = await getDatasetId(params.trainingFileList);
    if (!datasetIdToUse) return;

    // Train all selected models
    for (const modelValue of selectedModels.value) {
      const response = await executeTrain(
        {
          datasetId: datasetIdToUse,
          featureColumns: params.selectedFeatureColumns,
          targetColumn: params.selectedTargetColumn,
          model: modelValue,
          workItemId: params.workItemId,
        },
        "auto"
      );

      if (response) {
        registerTask(modelValue, response.taskId);
        activeLogTab.value = response.taskId.toString();
        pollTaskStatus(response.taskId, modelValue).then(() =>
          fetchTuningResults(params.workItemId)
        );
        pollTaskLogs(response.taskId);
      }
    }
  };

  /**
   * Start tuning a single model
   */
  const startSingleModelTuning = async (
    params: {
      trainingFileList: any[];
      selectedFeatureColumns: string[];
      selectedTargetColumn: string;
      workItemId?: number;
    },
    modelValue: string,
    paramGrid?: Record<string, any>,
    trainingType?: string,
    parentTaskId?: number
  ) => {
    const datasetIdToUse = await getDatasetId(params.trainingFileList);
    if (!datasetIdToUse) return;

    const response = await executeTrain(
      {
        datasetId: datasetIdToUse,
        featureColumns: params.selectedFeatureColumns,
        targetColumn: params.selectedTargetColumn,
        model: modelValue,
        paramGrid: paramGrid,
        workItemId: params.workItemId,
      },
      trainingType === "manual" ? "manual" : "auto"
    );

    if (response) {
      registerTask(modelValue, response.taskId, "pending");
      activeLogTab.value = response.taskId.toString();
      pollTaskStatus(response.taskId, modelValue).then(() =>
        fetchTuningResults(params.workItemId)
      );
      pollTaskLogs(response.taskId);
    }
  };

  /**
   * Reset tuning step state
   */
  const resetTuningStep = () => {
    selectedModels.value = [];
    selectedBestModel.value = null;
    selectedTaskId.value = null;
    activeLogTab.value = "";
    tuningResults.value = [];
    clearTasks();
  };

  return {
    // State
    selectedModels,
    activeLogTab,
    selectedBestModel,
    selectedTaskId,
    tuningResults,
    tuningStatus,
    tuningTasks,
    taskLogs,
    isTuning,

    // Actions
    fetchTuningResults,
    startBatchTuning,
    startSingleModelTuning,
    resetTuningStep,
  };
}
