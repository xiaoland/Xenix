<template>
  <div class="min-h-screen bg-gray-50 py-8">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <PageHeader />

      <div class="text-center mb-4">
        <a-breadcrumb>
          <a-breadcrumb-item>
            <NuxtLink to="/">{{ $t("navigation.home") }}</NuxtLink>
          </a-breadcrumb-item>
          <a-breadcrumb-item v-if="workItem">
            {{ workItem.name }}
          </a-breadcrumb-item>
        </a-breadcrumb>
      </div>

      <div v-if="isLoading" class="text-center py-8">
        <a-spin size="large" />
      </div>

      <div v-else-if="!workItem" class="text-center py-8">
        <a-result
          status="404"
          :title="$t('workItems.fetchError')"
          :sub-title="$t('workItems.fetchError')"
        >
          <template #extra>
            <a-button type="primary" @click="$router.push('/')">
              {{ $t("navigation.home") }}
            </a-button>
          </template>
        </a-result>
      </div>

      <div v-else>
        <div class="text-center mb-8">
          <h1 class="text-4xl font-bold text-gray-900 mb-2">
            {{ workItem.name }}
          </h1>
          <p class="text-lg text-gray-600" v-if="workItem.description">
            {{ workItem.description }}
          </p>
          <div class="mt-2">
            <a-tag :color="getStatusColor(workItem.status)">
              {{ $t(`workItems.${workItem.status}`) }}
            </a-tag>
          </div>
        </div>

        <a-card class="mb-6">
          <a-steps v-model:current="currentStep" class="mb-8">
            <a-step
              :title="$t('steps.upload.title')"
              :description="$t('steps.upload.description')"
            />
            <a-step
              :title="$t('steps.tune.title')"
              :description="$t('steps.tune.description')"
            />
            <a-step
              :title="$t('steps.predict.title')"
              :description="$t('steps.predict.description')"
            />
          </a-steps>

          <!-- Step 0: Upload (skipped if work item has upload data) -->
          <div v-if="currentStep === 0">
            <UploadStep
              v-model="trainingFileList"
              :project-id="workItem.projectId"
              @continue="handleColumnSelection"
            />
          </div>

          <!-- Step 1: Tuning -->
          <div v-if="currentStep === 1">
            <TuningStep
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
              @start-tuning="handleStartBatchTuning"
              @start-single-tune="handleStartSingleModelTuning"
              @continue="nextStep"
              @back="goToUploadStep"
            />
          </div>

          <!-- Step 2: Prediction -->
          <div v-if="currentStep === 2">
            <PredictionStep
              v-model="predictionFileList"
              :best-model="selectedBestModel"
              :is-predicting="isPredicting"
              :prediction-task="predictionTask"
              @predict="handleStartPrediction"
              @back="prevStep"
              @reset="reset"
            />
          </div>
        </a-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";
import { useWorkflowState } from "../../composables/useWorkflowState";
import { useDatasetRegistration } from "../../composables/useDatasetRegistration";
import { useTuningStep } from "../../composables/useTuningStep";
import { usePredictionStep } from "../../composables/usePredictionStep";
import { WorkItemService } from "../../services";
import { AVAILABLE_MODELS } from "../../constants/models";
import type { WorkItem } from "../../types";

const { t } = useI18n();
const route = useRoute();

// Work item data
const workItem = ref<WorkItem | null>(null);
const isLoading = ref(false);

// Available regression models
const availableModels = AVAILABLE_MODELS;

// Workflow state
const {
  currentStep,
  trainingFileList,
  selectedFeatureColumns,
  selectedTargetColumn,
  nextStep,
  prevStep,
  resetAll,
} = useWorkflowState();

// Dataset registration
const { uploadedDatasetId, clearDatasetId } = useDatasetRegistration();

// Tuning step logic
const {
  selectedModels,
  activeLogTab,
  selectedBestModel,
  selectedTaskId,
  tuningResults,
  tuningStatus,
  tuningTasks,
  taskLogs,
  isTuning,
  fetchTuningResults,
  startBatchTuning,
  startSingleModelTuning,
  resetTuningStep,
} = useTuningStep();

// Prediction step logic
const {
  predictionFileList,
  isPredicting,
  predictionTask,
  startPrediction,
  resetPredictionStep,
} = usePredictionStep();

const handleColumnSelection = async ({
  featureColumns,
  targetColumn,
  datasetId,
}: {
  featureColumns: string[];
  targetColumn: string;
  datasetId?: number;
}) => {
  selectedFeatureColumns.value = featureColumns;
  selectedTargetColumn.value = targetColumn;
  uploadedDatasetId.value = datasetId ? String(datasetId) : "";

  // Save upload step results to work item
  if (workItem.value) {
    try {
      const response = await WorkItemService.update(workItem.value.id, {
        datasetId: datasetId,
        featureColumns: featureColumns,
        targetColumn: targetColumn,
      });

      // Update local work item state with saved data
      if (response.success && response.workItem) {
        workItem.value = response.workItem;
      } else {
        // Fallback: update local state manually
        workItem.value.datasetId = datasetId;
        workItem.value.featureColumns = featureColumns;
        workItem.value.targetColumn = targetColumn;
      }

      message.success(t("messages.uploadDataSaved"));
    } catch (error) {
      console.error("Failed to save upload data:", error);
      // Update local state anyway so UI works
      workItem.value.datasetId = datasetId;
      workItem.value.featureColumns = featureColumns;
      workItem.value.targetColumn = targetColumn;
    }
  }

  // Move to tuning step
  currentStep.value = 1;

  // Fetch existing tuning results
  await fetchTuningResults(workItem.value?.id);

  message.success(t("messages.readyToTrain", { count: featureColumns.length }));
};

const goToUploadStep = () => {
  currentStep.value = 0;
};

const handleStartBatchTuning = async () => {
  await startBatchTuning({
    uploadedDatasetId: uploadedDatasetId.value,
    trainingFileList: trainingFileList.value,
    selectedFeatureColumns: selectedFeatureColumns.value,
    selectedTargetColumn: selectedTargetColumn.value,
    workItemId: workItem.value?.id,
  });
};

const handleStartSingleModelTuning = async (
  modelValue: string,
  paramGrid?: Record<string, any>,
  trainingType?: string,
  parentTaskId?: number
) => {
  await startSingleModelTuning(
    {
      uploadedDatasetId: uploadedDatasetId.value,
      trainingFileList: trainingFileList.value,
      selectedFeatureColumns: selectedFeatureColumns.value,
      selectedTargetColumn: selectedTargetColumn.value,
      workItemId: workItem.value?.id,
    },
    modelValue,
    paramGrid,
    trainingType,
    parentTaskId
  );
};

const handleStartPrediction = async () => {
  await startPrediction({
    selectedBestModel: selectedBestModel.value,
    tuningTasks: tuningTasks.value,
    uploadedDatasetId: uploadedDatasetId.value,
    selectedFeatureColumns: selectedFeatureColumns.value,
    selectedTargetColumn: selectedTargetColumn.value,
  });
};

const reset = () => {
  resetAll();
  clearDatasetId();
  resetTuningStep();
  resetPredictionStep();
};

const fetchWorkItem = async () => {
  const workItemId = route.params.id as string;
  if (!workItemId) return;

  isLoading.value = true;
  try {
    const response = await WorkItemService.fetchById(workItemId);
    if (response.success) {
      workItem.value = response.workItem;

      // Check if work item has saved upload data
      if (
        workItem.value.datasetId &&
        workItem.value.featureColumns &&
        workItem.value.targetColumn
      ) {
        // Restore upload data
        uploadedDatasetId.value = String(workItem.value.datasetId);
        selectedFeatureColumns.value = workItem.value.featureColumns;
        selectedTargetColumn.value = workItem.value.targetColumn;

        // Skip upload step, go directly to tuning
        currentStep.value = 1;

        // Fetch existing tuning results
        await fetchTuningResults(workItem.value.id);

        message.info(t("messages.uploadDataRestored"));
      } else {
        // Start from upload step
        currentStep.value = 0;
      }
    }
  } catch (error) {
    console.error("Failed to fetch work item:", error);
    message.error(t("workItems.fetchError"));
  } finally {
    isLoading.value = false;
  }
};

const getStatusColor = (status: string) => {
  switch (status) {
    case "active":
      return "green";
    case "completed":
      return "blue";
    case "archived":
      return "gray";
    default:
      return "default";
  }
};

onMounted(() => {
  fetchWorkItem();
});
</script>
