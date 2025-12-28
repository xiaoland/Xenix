<template>
  <div class="space-y-6">
    <h2 class="text-2xl font-semibold mb-4">{{ $t("tuning.title") }}</h2>

    <!-- Integrated Model Tuning Table -->
    <ModelTuningTable
      :available-models="availableModels"
      :selected-models="localSelectedModels"
      :tuning-status="tuningStatus"
      :tuning-tasks="tuningTasks"
      :tuning-results="tuningResults"
      :task-logs="taskLogs"
      :is-tuning="isTuning"
      :selected-task-id="localSelectedTaskId"
      @update:selected-models="localSelectedModels = $event"
      @update:selectedTaskId="localSelectedTaskId = $event"
      @start-tune="handleStartTune"
      @view-logs="handleViewLogs"
    />

    <!-- Best Model Selection -->
    <div v-if="tuningResults.length > 0" class="mt-6">
      <h3 class="text-lg font-medium mb-3">
        {{ $t("tuning.selectBestForPrediction") }}
      </h3>
      <p class="text-sm text-gray-600 mb-2">
        {{ $t("tuning.selectResultNote") }}
      </p>
      <a-alert
        v-if="!localSelectedTaskId"
        type="warning"
        :message="$t('tuning.noResultSelected')"
        show-icon
        class="mb-3"
      />
    </div>

    <!-- Navigation -->
    <div class="flex gap-4 mt-6">
      <a-button @click="emit('back')">{{ $t("tuning.back") }}</a-button>
      <a-button
        type="primary"
        :disabled="!localSelectedTaskId"
        @click="emit('continue')"
      >
        {{ $t("tuning.continue") }}
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const props = defineProps<{
  availableModels: Array<{ label: string; value: string }>;
  selectedModels: string[];
  tuningStatus: Record<string, string>;
  tuningTasks: Record<string, number>;
  isTuning: boolean;
  tuningResults: any[];
  taskLogs: Record<string, any[]>;
  activeLogTab: string;
  selectedBestModel: string | null;
  selectedTaskId?: number | null;
  uploadedDatasetId: string;
  featureColumns: string[];
  targetColumn: string;
}>();

const emit = defineEmits<{
  "start-tuning": [];
  "start-single-tune": [model: string, paramGrid?: Record<string, any>, trainingType?: string, parentTaskId?: number];
  back: [];
  continue: [];
  "update:selectedModels": [models: string[]];
  "update:activeLogTab": [tab: string];
  "update:selected-best-model": [model: string];
  "update:selectedTaskId": [taskId: number | null];
  "update:tuningStatus": [status: Record<string, string>];
  "update:tuningTasks": [tasks: Record<string, number>];
  "update:tuningResults": [results: any[]];
  "update:isTuning": [value: boolean];
}>();

const localSelectedModels = computed({
  get: () => props.selectedModels,
  set: (value) => emit("update:selectedModels", value),
});

const localActiveLogTab = computed({
  get: () => props.activeLogTab,
  set: (value) => emit("update:activeLogTab", value),
});

const localSelectedBestModel = computed({
  get: () => props.selectedBestModel,
  set: (value) => emit("update:selected-best-model", value || ""),
});

const localSelectedTaskId = computed({
  get: () => props.selectedTaskId,
  set: (value) => emit("update:selectedTaskId", value),
});

// Business logic: Start training for a single model
const handleStartTune = async (
  model: string,
  paramGrid?: Record<string, any>,
  trainingType?: string,
  parentTaskId?: number
) => {
  if (!props.uploadedDatasetId) {
    message.error(t("messages.uploadError"));
    return;
  }

  if (props.featureColumns.length === 0 || !props.targetColumn) {
    message.error(t("messages.columnSelectionError"));
    return;
  }

  emit("update:isTuning", true);
  
  const newStatus = { ...props.tuningStatus, [model]: "pending" };
  emit("update:tuningStatus", newStatus);

  try {
    const formData = new FormData();
    formData.append("datasetId", props.uploadedDatasetId);
    formData.append("model", model);
    formData.append("featureColumns", JSON.stringify(props.featureColumns));
    formData.append("targetColumn", props.targetColumn);

    if (paramGrid) {
      formData.append("paramGrid", JSON.stringify(paramGrid));
    }

    if (trainingType) {
      formData.append("trainingType", trainingType);
    }

    if (parentTaskId) {
      formData.append("parentTaskId", parentTaskId.toString());
    }

    const response = await $fetch("/api/upload", {
      method: "POST",
      body: formData,
    });

    if (response.success) {
      const newTasks = { ...props.tuningTasks, [model]: response.taskId };
      const updatedStatus = { ...newStatus, [model]: "running" };
      
      emit("update:tuningTasks", newTasks);
      emit("update:tuningStatus", updatedStatus);
      emit("update:activeLogTab", response.taskId.toString());

      // Start polling for this task
      pollTaskStatus(response.taskId, model);

      message.success(t("messages.tuningStarted"));
    }
  } catch (error) {
    const failedStatus = { ...newStatus, [model]: "failed" };
    emit("update:tuningStatus", failedStatus);
    message.error(t("messages.tuningFailed") + ": " + error.message);
  } finally {
    emit("update:isTuning", false);
  }
};

// Poll task status
const pollTaskStatus = async (taskId: number, modelValue?: string) => {
  const maxAttempts = 120;
  let attempts = 0;

  while (attempts < maxAttempts) {
    try {
      const response = await $fetch(`/api/task/${taskId}`);

      if (modelValue && response.task.status !== props.tuningStatus[modelValue]) {
        const updatedStatus = { ...props.tuningStatus, [modelValue]: response.task.status };
        emit("update:tuningStatus", updatedStatus);
      }

      if (response.task.status === "completed") {
        await fetchTuningResults();
        return response;
      }

      if (response.task.status === "failed") {
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

// Fetch tuning results
const fetchTuningResults = async () => {
  try {
    const taskIds = Object.values(props.tuningTasks);
    const results = await Promise.all(
      taskIds.map((taskId) =>
        $fetch(`/api/results/${taskId}`).catch(() => null)
      )
    );

    const validResults = results
      .filter((r) => r !== null && r.success && r.results)
      .map((r) => {
        const result = r.results;
        const model = result.model || Object.keys(props.tuningTasks).find(
          (k) => props.tuningTasks[k] === taskIds[results.indexOf(r)]
        );
        
        return {
          model: model,
          params: result.params,
          mse_train: result.metrics?.mse_train,
          mae_train: result.metrics?.mae_train,
          r2_train: result.metrics?.r2_train,
          mse_test: result.metrics?.mse_test,
          mae_test: result.metrics?.mae_test,
          r2_test: result.metrics?.r2_test,
          status: props.tuningStatus[model] || "completed",
        };
      });

    emit("update:tuningResults", validResults);
  } catch (error) {
    console.error("Failed to fetch tuning results:", error);
  }
};

const handleViewLogs = (taskId: string, modelName: string) => {
  emit("update:activeLogTab", taskId);
};

const formatModelName = (name: string) => {
  return name.replace(/_/g, " ");
};

const formatMetric = (value: string | number) => {
  if (!value) return "N/A";
  const num = typeof value === "string" ? parseFloat(value) : value;
  return num.toFixed(4);
};
</script>
