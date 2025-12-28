<template>
  <div class="min-h-screen bg-gray-50 py-8">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <PageHeader />

      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-gray-900 mb-2">
          {{ $t("app.title") }}
        </h1>
        <p class="text-lg text-gray-600">
          {{ $t("app.subtitle") }}
        </p>
      </div>

      <a-card class="mb-6">
        <a-steps :current="currentStep" class="mb-8">
          <a-step
            :title="$t('steps.uploadTrain.title')"
            :description="$t('steps.uploadTrain.description')"
          />
          <a-step
            :title="$t('steps.predict.title')"
            :description="$t('steps.predict.description')"
          />
        </a-steps>

        <!-- Step 1: Upload & Train -->
        <div v-if="currentStep === 0">
          <!-- Upload Section (shown first) -->
          <UploadStep
            v-if="!hasUploadedData"
            v-model="trainingFileList"
            @continue="handleColumnSelection"
          />

          <!-- Tuning Section (shown after upload) -->
          <TuningStep
            v-else
            v-model:selected-models="selectedModels"
            v-model:active-log-tab="activeLogTab"
            v-model:selected-best-model="selectedBestModel"
            v-model:selected-task-id="selectedTaskId"
            :available-models="availableModels"
            :tuning-status="tuningStatus"
            :tuning-tasks="tuningTasks"
            :is-tuning="isTuning"
            :tuning-results="tuningResults"
            :task-logs="taskLogs"
            @start-tuning="startTuning"
            @start-single-tune="startSingleModelTuning"
            @continue="nextStep"
            @back="resetUploadAndClearData"
          />
        </div>

        <!-- Step 2: Prediction -->
        <PredictionStep
          v-if="currentStep === 1"
          v-model="predictionFileList"
          :best-model="selectedBestModel"
          :is-predicting="isPredicting"
          :prediction-task="predictionTask"
          @predict="startPrediction"
          @back="prevStep"
          @reset="reset"
        />
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";
import { useWorkflowState } from "../composables/useWorkflowState";
import { useTaskPolling } from "../composables/useTaskPolling";
import { useDatasetRegistration } from "../composables/useDatasetRegistration";
import { useModelTraining } from "../composables/useModelTraining";
import { ApiService } from "../services/apiService";
import { AVAILABLE_MODELS } from "../constants/models";

const { t } = useI18n();

// Available regression models
const availableModels = AVAILABLE_MODELS;

// Workflow state
const {
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
  nextStep,
  prevStep,
  resetAll,
  resetUpload,
} = useWorkflowState();

// Task polling
const {
  tuningStatus,
  tuningTasks,
  taskLogs,
  pollTaskLogs,
  pollTaskStatus,
  registerTask,
  clearTasks,
} = useTaskPolling();

// Dataset registration
const { uploadedDatasetId, registerFileAsDataset, clearDatasetId } =
  useDatasetRegistration();

// Model training
const { isTuning, executeTrain } = useModelTraining();

const handleColumnSelection = ({
  featureColumns,
  targetColumn,
  datasetId,
}: {
  featureColumns: string[];
  targetColumn: string;
  datasetId?: string;
}) => {
  selectedFeatureColumns.value = featureColumns;
  selectedTargetColumn.value = targetColumn;
  uploadedDatasetId.value = datasetId || "";
  hasUploadedData.value = true;
  message.success(t("messages.readyToTrain", { count: featureColumns.length }));
};

const resetUploadAndClearData = () => {
  resetUpload();
  clearDatasetId();
  clearTasks();
};

const startTuning = async () => {
  // Validate that we have training data
  if (!uploadedDatasetId.value && trainingFileList.value.length === 0) {
    message.error(t("messages.uploadError"));
    return;
  }

  // Register file as dataset if needed
  let datasetIdToUse = uploadedDatasetId.value;
  if (!datasetIdToUse && trainingFileList.value.length > 0) {
    const file = trainingFileList.value[0].originFileObj;
    const registeredId = await registerFileAsDataset(file);
    if (registeredId) {
      datasetIdToUse = registeredId;
    }
  }

  if (!datasetIdToUse) {
    message.error(t("messages.datasetRegistrationFailed"));
    return;
  }

  // Train all selected models
  for (const modelValue of selectedModels.value) {
    const response = await executeTrain(
      {
        datasetId: datasetIdToUse,
        featureColumns: selectedFeatureColumns.value,
        targetColumn: selectedTargetColumn.value,
        model: modelValue,
      },
      "auto"
    );

    if (response) {
      registerTask(modelValue, response.taskId);
      activeLogTab.value = response.taskId.toString();
      pollTaskStatus(response.taskId, modelValue).then(fetchTuningResults);
      pollTaskLogs(response.taskId);
    }
  }
};

const startSingleModelTuning = async (
  modelValue: string,
  paramGrid?: Record<string, any>,
  trainingType?: string,
  parentTaskId?: number
) => {
  // Register file as dataset if needed
  let datasetIdToUse = uploadedDatasetId.value;
  if (!datasetIdToUse && trainingFileList.value.length > 0) {
    const file = trainingFileList.value[0].originFileObj;
    const registeredId = await registerFileAsDataset(file);
    if (registeredId) {
      datasetIdToUse = registeredId;
    }
  }

  if (!datasetIdToUse) {
    message.error(t("messages.datasetRegistrationFailed"));
    return;
  }

  const response = await executeTrain(
    {
      datasetId: datasetIdToUse,
      featureColumns: selectedFeatureColumns.value,
      targetColumn: selectedTargetColumn.value,
      model: modelValue,
      paramGrid: paramGrid,
    },
    trainingType === "manual" ? "manual" : "auto"
  );

  if (response) {
    registerTask(modelValue, response.taskId, "pending");
    activeLogTab.value = response.taskId.toString();
    pollTaskStatus(response.taskId, modelValue).then(fetchTuningResults);
    pollTaskLogs(response.taskId);
  }
};

const fetchTuningResults = async () => {
  try {
    const taskIds = Object.values(tuningTasks.value);
    const results = await Promise.all(
      taskIds.map((taskId) =>
        ApiService.fetchTaskResults(taskId).catch(() => null)
      )
    );

    const validResults = results
      .filter((r) => r !== null && r.success && r.results)
      .map((r) => {
        const result = r!.results;
        const model = result.model || Object.keys(tuningTasks.value).find(
          (k) => tuningTasks.value[k] === taskIds[results.indexOf(r)]
        );
        
        return {
          model: model!,
          params: result.params,
          metrics: {
            mse_train: result.metrics?.mse_train,
            mae_train: result.metrics?.mae_train,
            r2_train: result.metrics?.r2_train,
            mse_test: result.metrics?.mse_test,
            mae_test: result.metrics?.mae_test,
            r2_test: result.metrics?.r2_test,
          },
          status: tuningStatus.value[model!] || "completed",
        };
      });

    tuningResults.value = validResults;
  } catch (error) {
    console.error("Failed to fetch tuning results:", error);
  }
};

const startPrediction = async () => {
  if (!selectedBestModel.value) {
    message.error(t("messages.selectModelError"));
    return;
  }

  if (predictionFileList.value.length === 0) {
    message.error(t("messages.uploadPredictionError"));
    return;
  }

  if (!uploadedDatasetId.value) {
    message.error(t("messages.trainingDatasetError"));
    return;
  }

  const selectedModelTaskId = tuningTasks.value[selectedBestModel.value];
  if (!selectedModelTaskId) {
    message.error(t("messages.tuningTaskError"));
    return;
  }

  isPredicting.value = true;

  try {
    const response = await ApiService.startPrediction({
      file: predictionFileList.value[0].originFileObj,
      model: selectedBestModel.value,
      tuningTaskId: selectedModelTaskId,
      trainingDatasetId: uploadedDatasetId.value,
      featureColumns: selectedFeatureColumns.value,
      targetColumn: selectedTargetColumn.value,
    });

    if (response.success) {
      predictionTask.value = { taskId: response.taskId, status: "running" };
      message.success(t("messages.predictionStarted"));

      const result = await pollTaskStatus(response.taskId);

      if (result && result.task.status === "completed") {
        predictionTask.value.status = "completed";
        const taskResult: any = result.task.result || {};
        const taskParameter: any = result.task.parameter || {};
        predictionTask.value.outputFile = taskResult.outputFile || taskParameter.outputFile || response.outputFile;
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

const reset = () => {
  resetAll();
  clearDatasetId();
  clearTasks();
};
</script>
