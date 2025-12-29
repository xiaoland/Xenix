/**
 * Composable for managing the main workflow state
 */

import { ref } from "vue";
import type { TuningResult, PredictionTask } from "~/types";

export function useWorkflowState() {
  // Step management
  const currentStep = ref(0);
  const trainingFileList = ref([]);
  const predictionFileList = ref([]);
  const hasUploadedData = ref(false);

  // Model and column selection
  const selectedModels = ref<string[]>([]);
  const selectedFeatureColumns = ref<string[]>([]);
  const selectedTargetColumn = ref<string>("");
  const selectedBestModel = ref<string | null>(null);
  const selectedTaskId = ref<number | null>(null);

  // Prediction state
  const isPredicting = ref(false);
  const predictionTask = ref<PredictionTask | null>(null);

  // Logs state
  const activeLogTab = ref<string>("");

  // Tuning results
  const tuningResults = ref<TuningResult[]>([]);

  // Navigation
  const nextStep = () => {
    if (currentStep.value < 1) {
      currentStep.value++;
    }
  };

  const prevStep = () => {
    if (currentStep.value > 0) {
      currentStep.value--;
    }
  };

  // Reset all state
  const resetAll = () => {
    currentStep.value = 0;
    trainingFileList.value = [];
    predictionFileList.value = [];
    hasUploadedData.value = false;
    selectedModels.value = [];
    selectedFeatureColumns.value = [];
    selectedTargetColumn.value = "";
    selectedBestModel.value = null;
    selectedTaskId.value = null;
    isPredicting.value = false;
    predictionTask.value = null;
    activeLogTab.value = "";
    tuningResults.value = [];
  };

  // Reset upload state
  const resetUpload = () => {
    hasUploadedData.value = false;
    trainingFileList.value = [];
    selectedModels.value = [];
    selectedFeatureColumns.value = [];
    selectedTargetColumn.value = "";
    tuningResults.value = [];
    selectedBestModel.value = null;
  };

  return {
    // State
    currentStep,
    trainingFileList,
    predictionFileList,
    hasUploadedData,
    selectedModels,
    selectedFeatureColumns,
    selectedTargetColumn,
    selectedBestModel,
    selectedTaskId,
    isPredicting,
    predictionTask,
    activeLogTab,
    tuningResults,

    // Actions
    nextStep,
    prevStep,
    resetAll,
    resetUpload,
  };
}
