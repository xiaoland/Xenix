<template>
  <div class="space-y-6">
    <h2 class="text-2xl font-semibold mb-4">
      {{ $t("components.ml.tuning.title") }}
    </h2>

    <a-alert
      :message="$t('components.ml.tuning.trainDescription')"
      type="info"
      show-icon
      class="mb-4"
    />

    <!-- Model Selection -->
    <div class="bg-white rounded-lg border p-4 mb-4">
      <h3 class="text-lg font-medium mb-3">
        {{ $t("components.ml.tuning.selectModels") }}
      </h3>
      <a-select
        v-model:value="selectedModels"
        mode="multiple"
        :placeholder="$t('components.ml.tuning.selectPlaceholder')"
        style="width: 100%"
        :options="availableModels"
        class="mb-3"
      />

      <div class="flex gap-2">
        <a-button
          type="primary"
          class="inline-flex items-center"
          :loading="isTraining"
          :disabled="selectedModels.length === 0"
          @click="handleStartAutoTune"
        >
          <span class="i-mdi-auto-fix mr-1"></span>
          {{ $t("components.ml.tuning.startAutoTune") }}
        </a-button>
        <a-button
          :disabled="tasks?.length === 0"
          danger
          class="inline-flex items-center"
          @click="handleClearFailedTasks"
        >
          <span class="i-mdi-delete-outline mr-1"></span>
          {{ $t("components.ml.tuning.clearFailedTasks") }}
        </a-button>
      </div>
    </div>

    <!-- Tasks Table -->
    <div class="bg-white rounded-lg border">
      <div class="px-4 py-3 border-b bg-gray-50">
        <h3 class="text-lg font-medium">Training Tasks</h3>
      </div>

      <a-table
        :columns="columns"
        :data-source="tasks"
        :loading="loading"
        :pagination="false"
        row-key="id"
        size="small"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'model'">
            <span class="font-medium">{{
              formatModelName(record.parameter?.model)
            }}</span>
          </template>

          <template v-else-if="column.key === 'status'">
            <a-tag :color="getStatusColor(record.status)">
              {{ record.status }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'metrics'">
            <div
              v-if="record.status === 'completed' && record.result?.params"
              class="text-sm"
            >
              <div
                v-for="(value, key) in getDisplayMetrics(record.result)"
                :key="key"
              >
                <span class="text-gray-600">{{ key }}:</span>
                <span class="ml-1 font-medium">{{ formatMetric(value) }}</span>
              </div>
            </div>
            <span
              v-else-if="record.status === 'failed'"
              class="text-red-500 text-sm"
            >
              {{ record.error || "Training failed" }}
            </span>
            <span v-else class="text-gray-400 text-sm">-</span>
          </template>

          <template v-else-if="column.key === 'action'">
            <a-radio
              :checked="selectedTaskId === record.id"
              :disabled="record.status !== 'completed'"
              @click="handleSelectTask(record.id)"
            >
              Select
            </a-radio>
          </template>
        </template>
      </a-table>

      <div
        v-if="tasks?.length === 0 && !loading"
        class="text-center py-8 text-gray-500"
      >
        No training tasks yet. Select models and start training.
      </div>
    </div>

    <!-- Navigation -->
    <div class="flex justify-between">
      <a-button @click="emit('back')"> Back to Prepare </a-button>
      <a-button
        type="primary"
        :disabled="!selectedTaskId"
        @click="handleContinue"
      >
        Continue to Predict
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { message } from "ant-design-vue";

import { onMounted, onUnmounted, ref } from "vue";

import type { Task } from "@xenix/shared";

import { client } from "../../../api/client";
import { AVAILABLE_MODELS } from "../../../constants/models";
import { POLLING_CONFIG } from "../../../constants/config";
import { useTasks } from "@/composables";

const props = defineProps<{
  workItemId: number;
  datasetId: number | null;
  featureColumns: string[];
  targetColumn: string;
}>();

const emit = defineEmits<{
  continue: [
    data: { model: string; parameters: Record<string, any>; taskId: number },
  ];
  back: [];
}>();

// State
const selectedModels = ref<string[]>([]);
const selectedTaskId = ref<number | null>(null);
const isTraining = ref(false);

// Available models
const availableModels = AVAILABLE_MODELS.map((m) => ({
  label: m.label,
  value: m.value,
}));

// Table columns
const columns = [
  { title: "Model", key: "model", width: 200 },
  { title: "Status", key: "status", width: 120 },
  { title: "Metrics / Error", key: "metrics" },
  { title: "Action", key: "action", width: 100 },
];

// Polling interval
let pollInterval: number | null = null;

/**
 * Fetch tuning tasks for the work item
 */
const {
  data: tasks,
  isLoading: loading,
  refetch: fetchTasks,
} = useTasks({
  workItemId: String(props.workItemId),
  types: "auto-tune,manual-tune",
});

/**
 * Start auto-tune for selected models
 */
const handleStartAutoTune = async () => {
  isTraining.value = true;
  try {
    // Start training for each selected model
    for (const model of selectedModels.value) {
      const response = await client.tune["auto-tune"].$post({
        json: {
          datasetId: props.datasetId ?? undefined,
          featureColumns: props.featureColumns,
          targetColumn: props.targetColumn,
          model,
          workItemId: props.workItemId,
        },
      });
      if (!response.ok) throw new Error("Failed to start auto tune");
    }
    message.success(
      `Started training for ${selectedModels.value.length} model(s)`
    );
    selectedModels.value = [];
    await fetchTasks();
    startPolling();
  } catch (error: any) {
    console.error("Failed to start training:", error);
    message.error(error.message || "Failed to start training");
  } finally {
    isTraining.value = false;
  }
};

/**
 * Clear all failed tasks
 */
const handleClearFailedTasks = async () => {
  try {
    // NOTE: Backend endpoint for bulk task deletion not yet implemented
    // Future: Implement DELETE /api/tasks/failed endpoint
    // await TaskService.deleteFailedTasks(props.workItemId);
    message.info("Task deletion feature coming soon");
    // await fetchTasks();
  } catch (error: any) {
    console.error("Failed to clear tasks:", error);
    message.error(error.message || "Failed to clear tasks");
  }
};

/**
 * Select a task to continue
 */
const handleSelectTask = (taskId: number) => {
  selectedTaskId.value = taskId;
};

/**
 * Continue to prediction step
 */
const handleContinue = async () => {
  if (!selectedTaskId.value) return;

  try {
    const response = await client.tasks[":id"].$get({
      param: { id: String(selectedTaskId.value) },
    });
    if (!response.ok) throw new Error("Failed to fetch task");
    const data = (await response.json()) as any;
    if (data.task) {
      emit("continue", {
        model: data.task.parameter?.model || "",
        parameters: data.task.result?.params || {},
        taskId: selectedTaskId.value,
      });
    }
  } catch (error: any) {
    console.error("Failed to fetch task:", error);
    message.error(error.message || "Failed to fetch task details");
  }
};

/**
 * Start polling for task updates
 */
const startPolling = () => {
  if (pollInterval) return;
  pollInterval = window.setInterval(() => {
    const hasRunningTasks = (tasks.value ?? []).some(
      (t) => t.status === "pending" || t.status === "running"
    );
    if (hasRunningTasks) {
      fetchTasks();
    } else {
      stopPolling();
    }
  }, POLLING_CONFIG.DEFAULT_INTERVAL);
};

/**
 * Stop polling
 */
const stopPolling = () => {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
};

/**
 * Get status color
 */
const getStatusColor = (status: string) => {
  switch (status) {
    case "completed":
      return "success";
    case "failed":
      return "error";
    case "running":
      return "processing";
    case "pending":
      return "default";
    default:
      return "default";
  }
};

/**
 * Format model name
 */
const formatModelName = (modelValue?: string) => {
  if (!modelValue) return "-";
  const model = AVAILABLE_MODELS.find((m) => m.value === modelValue);
  return model ? model.label : modelValue;
};

/**
 * Format metric value
 */
const formatMetric = (value: any) => {
  if (typeof value === "number") {
    return value.toFixed(4);
  }
  return value;
};

/**
 * Get display metrics from result
 */
const getDisplayMetrics = (result: any) => {
  if (!result || !result.params) return {};
  // Show a subset of important metrics
  const metrics: Record<string, any> = {};
  if (result.score !== undefined) metrics["Score"] = result.score;
  if (result.params) {
    const paramCount = Object.keys(result.params).length;
    metrics["Parameters"] = `${paramCount} params`;
  }
  return metrics;
};

// Lifecycle
onMounted(async () => {
  await fetchTasks();
  const hasRunningTasks = (tasks.value ?? []).some(
    (t) => t.status === "pending" || t.status === "running"
  );
  if (hasRunningTasks) {
    startPolling();
  }
});

onUnmounted(() => {
  stopPolling();
});
</script>
