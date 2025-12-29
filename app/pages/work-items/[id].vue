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
          <a-steps :current="currentStep" class="mb-8">
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
              @start-tuning="startTuning"
              @start-single-tune="startSingleModelTuning"
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
              @predict="startPrediction"
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
import { useTaskPolling } from "../../composables/useTaskPolling";
import { useDatasetRegistration } from "../../composables/useDatasetRegistration";
import { useModelTraining } from "../../composables/useModelTraining";
import { TaskService, PredictionService } from "../../services";
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
      await $fetch(`/api/work-items/${workItem.value.id}`, {
        method: 'PUT',
        body: {
          datasetId: datasetId,
          featureColumns: featureColumns,
          targetColumn: targetColumn,
        },
      });
      message.success(t("messages.uploadDataSaved"));
    } catch (error) {
      console.error("Failed to save upload data:", error);
      // Continue anyway, data is in memory
    }
  }

  // Move to tuning step
  currentStep.value = 1;
  
  // Fetch existing tuning results
  await fetchTuningResults();
  
  message.success(t("messages.readyToTrain", { count: featureColumns.length }));
};

const goToUploadStep = () => {
  currentStep.value = 0;
};

const resetUploadAndClearData = () => {
  resetUpload();
  clearDatasetId();
  clearTasks();
  currentStep.value = 0;
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
        workItemId: workItem.value?.id, // Pass work item ID
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
      workItemId: workItem.value?.id, // Pass work item ID
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
  if (!workItem.value) return;
  
  try {
    // Fetch all tasks for this work item
    const response = await $fetch(`/api/work-items/${workItem.value.id}`);
    if (response.success && response.workItem.tasks) {
      const tasks = response.workItem.tasks.filter((t: any) => 
        t.type === 'auto-tune' && t.status === 'completed'
      );
      
      // Build tuning results from completed tasks
      tuningResults.value = tasks.map((task: any) => ({
        model: task.parameter?.model || '',
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
        trainingType: task.parameter?.trainingType || 'auto',
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
    const response = await PredictionService.start({
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

const fetchWorkItem = async () => {
  const workItemId = route.params.id as string;
  if (!workItemId) return;

  isLoading.value = true;
  try {
    const response = await $fetch(`/api/work-items/${workItemId}`);
    if (response.success) {
      workItem.value = response.workItem;
      
      // Check if work item has saved upload data
      if (workItem.value.datasetId && workItem.value.featureColumns && workItem.value.targetColumn) {
        // Restore upload data
        uploadedDatasetId.value = String(workItem.value.datasetId);
        selectedFeatureColumns.value = workItem.value.featureColumns;
        selectedTargetColumn.value = workItem.value.targetColumn;
        
        // Skip upload step, go directly to tuning
        currentStep.value = 1;
        
        // Fetch existing tuning results
        await fetchTuningResults();
        
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
