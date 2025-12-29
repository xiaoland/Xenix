/**
 * Composable for managing prediction step logic
 * Handles prediction execution and result downloads
 */

import { ref } from "vue";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";
import { PredictionService } from "~/services";
import { useTaskPolling } from "./useTaskPolling";
import type { PredictionTask } from "~/types";

export function usePredictionStep() {
  const { t } = useI18n();
  const { pollTaskStatus } = useTaskPolling();

  // Local state
  const predictionFileList = ref<any[]>([]);
  const isPredicting = ref(false);
  const predictionTask = ref<PredictionTask | null>(null);

  /**
   * Validate file before upload
   */
  const beforeUpload = (file: File) => {
    const isExcel = file.name.endsWith(".xlsx") || file.name.endsWith(".xls");
    if (!isExcel) {
      message.error(t("prediction.excelOnly"));
    }
    return false; // Prevent auto upload
  };

  /**
   * Start prediction with uploaded file
   */
  const startPrediction = async (params: {
    selectedBestModel: string | null;
    tuningTasks: Record<string, number>;
    uploadedDatasetId: string;
    selectedFeatureColumns: string[];
    selectedTargetColumn: string;
  }) => {
    if (!params.selectedBestModel) {
      message.error(t("messages.selectModelError"));
      return;
    }

    if (predictionFileList.value.length === 0) {
      message.error(t("messages.uploadPredictionError"));
      return;
    }

    if (!params.uploadedDatasetId) {
      message.error(t("messages.trainingDatasetError"));
      return;
    }

    const selectedModelTaskId = params.tuningTasks[params.selectedBestModel];
    if (!selectedModelTaskId) {
      message.error(t("messages.tuningTaskError"));
      return;
    }

    isPredicting.value = true;

    try {
      const response = await PredictionService.start({
        file: predictionFileList.value[0].originFileObj,
        model: params.selectedBestModel,
        tuningTaskId: selectedModelTaskId,
        trainingDatasetId: params.uploadedDatasetId,
        featureColumns: params.selectedFeatureColumns,
        targetColumn: params.selectedTargetColumn,
      });

      if (response.success) {
        predictionTask.value = { taskId: response.taskId, status: "running" };
        message.success(t("messages.predictionStarted"));

        const result = await pollTaskStatus(response.taskId);

        if (result && result.task.status === "completed") {
          predictionTask.value.status = "completed";
          const taskResult: any = result.task.result || {};
          const taskParameter: any = result.task.parameter || {};
          predictionTask.value.outputFile =
            taskResult.outputFile ||
            taskParameter.outputFile ||
            response.outputFile;
          predictionTask.value.taskId = result.task.id;
          message.success(
            t("messages.predictionCompleted", {
              path: predictionTask.value.outputFile,
            })
          );
        } else if (result && result.task.status === "failed") {
          predictionTask.value.status = "failed";
          predictionTask.value.error = result.task.error;
          message.error(
            t("messages.predictionFailed", { error: result.task.error })
          );
        }
      }
    } catch (error: any) {
      message.error(t("messages.predictionError") + ": " + error.message);
    } finally {
      isPredicting.value = false;
    }
  };

  /**
   * Download prediction results
   */
  const downloadResults = () => {
    if (predictionTask.value?.taskId) {
      const downloadUrl = `/api/download/${predictionTask.value.taskId}`;
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = "";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      message.success(t("prediction.downloading"));
    }
  };

  /**
   * Reset prediction step state
   */
  const resetPredictionStep = () => {
    predictionFileList.value = [];
    isPredicting.value = false;
    predictionTask.value = null;
  };

  return {
    // State
    predictionFileList,
    isPredicting,
    predictionTask,

    // Actions
    beforeUpload,
    startPrediction,
    downloadResults,
    resetPredictionStep,
  };
}
