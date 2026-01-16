<template>
  <div class="space-y-6">
    <h2 class="text-2xl font-semibold mb-4">
      {{ $t("ml.tuning.title") }}
    </h2>

    <a-alert
      :message="$t('ml.tuning.trainDescription')"
      type="info"
      show-icon
      class="mb-4"
    />

    <!-- Model Selection and Actions -->
    <div class="bg-white rounded-lg border p-4 mb-4">
      <h3 class="text-lg font-medium mb-3">
        {{ $t("ml.tuning.selectModels") }}
      </h3>
      <a-select
        v-model:value="selectedModels"
        mode="multiple"
        :placeholder="$t('ml.tuning.selectPlaceholder')"
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
          {{ $t("ml.tuning.startAutoTune") }}
        </a-button>
        <a-button
          class="inline-flex items-center"
          @click="showManualTuneDialog = true"
        >
          <span class="i-mdi-tune mr-1"></span>
          {{ $t("ml.tuning.manualTune") }}
        </a-button>
        <a-button
          :disabled="tasks?.length === 0"
          danger
          class="inline-flex items-center"
          @click="handleClearFailedTasks"
        >
          <span class="i-mdi-delete-outline mr-1"></span>
          {{ $t("ml.tuning.clearFailedTasks") }}
        </a-button>
      </div>
    </div>

    <!-- Tasks Table -->
    <div class="bg-white rounded-lg border">
      <div class="px-4 py-3 border-b bg-gray-50">
        <h3 class="text-lg font-medium">
          {{ $t("ml.tuning.trainingTasks") }}
        </h3>
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
          <!-- Model Column -->
          <template v-if="column.key === 'model'">
            <span class="font-medium">{{
              formatModelName(record.parameter?.model)
            }}</span>
          </template>

          <!-- Type Column -->
          <template v-else-if="column.key === 'type'">
            <a-tag
              v-if="record.type === 'auto-tune'"
              color="blue"
              class="min-w-[60px] text-center"
            >
              {{ $t("ml.tuning.type.auto") }}
            </a-tag>
            <a-tag
              v-else-if="record.type === 'manual-tune'"
              color="green"
              class="min-w-[60px] text-center"
            >
              {{ $t("ml.tuning.type.manual") }}
            </a-tag>
          </template>

          <!-- Status Column -->
          <template v-else-if="column.key === 'status'">
            <a-tag :color="getStatusColor(record.status)">
              {{ $t(`ml.tuning.status.${record.status}`) }}
            </a-tag>
          </template>

          <!-- Metrics Column -->
          <template v-else-if="column.key === 'metrics'">
            <div
              v-if="record.status === 'completed' && record.result?.metrics"
              class="text-sm"
            >
              <div
                v-for="(value, key) in getDisplayMetrics(record.result.metrics)"
                :key="key"
                class="inline-block mr-3"
              >
                <span class="text-gray-600">{{ formatMetricKey(key) }}:</span>
                <span class="ml-1 font-medium">{{ formatMetric(value) }}</span>
              </div>
            </div>
            <span
              v-else-if="record.status === 'failed'"
              class="text-red-500 text-sm"
            >
              {{ record.error || "Training failed" }}
            </span>
            <span
              v-else-if="record.status === 'running'"
              class="text-blue-500 text-sm"
            >
              {{ $t("ml.tuning.training") }}
            </span>
            <span v-else class="text-gray-400 text-sm">-</span>
          </template>

          <!-- Actions Column -->
          <template v-else-if="column.key === 'action'">
            <div class="flex items-center gap-2">
              <a-radio
                :checked="selectedTaskId === record.id"
                :disabled="record.status !== 'completed'"
                @click="handleSelectTask(record.id)"
              >
                {{ $t("ml.tuning.select") }}
              </a-radio>
              <a-button
                v-if="
                  record.status === 'completed' &&
                  record.result?.params &&
                  Object.keys(record.result.params).length > 0
                "
                size="small"
                class="inline-flex items-center"
                @click="handleViewParams(record)"
              >
                <span class="i-mdi-eye-outline mr-1"></span>
                {{ $t("ml.tuning.viewParams") }}
              </a-button>
            </div>
          </template>
        </template>
      </a-table>

      <div
        v-if="tasks?.length === 0 && !loading"
        class="text-center py-8 text-gray-500"
      >
        {{ $t("ml.tuning.noTasks") }}
      </div>
    </div>

    <!-- Navigation -->
    <div class="flex justify-between">
      <a-button @click="emit('back')">
        {{ $t("ml.tuning.backToPrepare") }}
      </a-button>
      <a-button
        type="primary"
        :disabled="!selectedTaskId"
        @click="handleContinue"
      >
        {{ $t("ml.tuning.continueToPredict") }}
      </a-button>
    </div>

    <!-- Manual Tune Dialog -->
    <ManualTuneDialog v-model="showManualTuneDialog" @tune="handleManualTune" />

    <!-- View Params Modal -->
    <a-modal
      v-model:open="showParamsModal"
      :title="$t('ml.tuning.paramsModalTitle')"
      width="600px"
      :footer="null"
    >
      <div v-if="selectedTaskForParams" class="params-display">
        <div class="mb-4">
          <h4 class="text-sm font-medium mb-2">
            {{ $t("ml.tuning.model") }}:
            {{ formatModelName(selectedTaskForParams.parameter?.model) }}
          </h4>
          <a-tag :color="getStatusColor(selectedTaskForParams.status)">
            {{ selectedTaskForParams.status }}
          </a-tag>
          <a-tag
            v-if="selectedTaskForParams.type === 'auto-tune'"
            color="blue"
            class="ml-2"
          >
            {{ $t("ml.tuning.type.auto") }}
          </a-tag>
          <a-tag
            v-else-if="selectedTaskForParams.type === 'manual-tune'"
            color="green"
            class="ml-2"
          >
            {{ $t("ml.tuning.type.manual") }}
          </a-tag>
        </div>

        <!-- Parameters -->
        <div class="bg-gray-50 rounded p-4 mb-4">
          <h4 class="text-sm font-semibold mb-3">
            {{ $t("ml.tuning.parameters") }}
          </h4>
          <div
            v-for="(value, key) in selectedTaskForParams.result?.params"
            :key="key"
            class="param-row py-2 border-b border-gray-200 last:border-0"
          >
            <span class="param-key text-gray-600 font-medium">{{ key }}:</span>
            <span class="param-value ml-2 font-mono text-sm">{{
              formatParamValue(value)
            }}</span>
          </div>
        </div>

        <!-- Metrics -->
        <div
          v-if="selectedTaskForParams.result?.metrics"
          class="bg-blue-50 rounded p-4"
        >
          <h4 class="text-sm font-semibold mb-3">
            {{ $t("ml.tuning.metrics") }}
          </h4>
          <div
            v-for="(value, key) in selectedTaskForParams.result.metrics"
            :key="key"
            class="metric-row py-2 border-b border-blue-100 last:border-0"
          >
            <span class="metric-key text-gray-600 font-medium">{{
              formatMetricKey(key)
            }}</span
            >:
            <span class="metric-value ml-2 font-mono text-sm font-medium">{{
              formatMetric(value)
            }}</span>
          </div>
        </div>
      </div>
    </a-modal>
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
import ManualTuneDialog from "./ManualTuneDialog.vue";

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
const showManualTuneDialog = ref(false);
const showParamsModal = ref(false);
const selectedTaskForParams = ref<Task | null>(null);

// Available models
const availableModels = AVAILABLE_MODELS.map((m) => ({
  label: m.label,
  value: m.value,
}));

// Table columns
const columns = [
  {
    title: "Model",
    key: "model",
    width: 180,
  },
  {
    title: "Type",
    key: "type",
    width: 80,
  },
  {
    title: "Status",
    key: "status",
    width: 100,
  },
  {
    title: "Metrics",
    key: "metrics",
  },
  {
    title: "Actions",
    key: "action",
    width: 200,
  },
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
  type: "auto-tune,manual-tune",
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
 * Handle manual tune submission
 */
const handleManualTune = async (data: {
  model: string;
  parameters: Record<string, any>;
}) => {
  try {
    const response = await client.tune["manual-tune"].$post({
      json: {
        datasetId: props.datasetId ?? undefined,
        featureColumns: props.featureColumns,
        targetColumn: props.targetColumn,
        model: data.model,
        parameters: data.parameters,
        workItemId: props.workItemId,
      },
    });
    if (!response.ok) throw new Error("Failed to start manual tune");

    message.success("Manual training started");
    await fetchTasks();
    startPolling();
  } catch (error: any) {
    console.error("Failed to start manual tune:", error);
    message.error(error.message || "Failed to start manual training");
  }
};

/**
 * Clear all failed tasks
 */
const handleClearFailedTasks = async () => {
  try {
    message.info("Task deletion feature coming soon");
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
 * View task parameters
 */
const handleViewParams = (task: Task) => {
  selectedTaskForParams.value = task;
  showParamsModal.value = true;
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
    const data = await response.json();
    if (data) {
      emit("continue", {
        model: data.parameter?.model || "",
        parameters: data.result?.params || {},
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
 * Format metric key (convert snake_case to Title Case)
 */
const formatMetricKey = (key: string) => {
  return key
    .replace(/_/g, " ")
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
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
 * Format parameter value
 */
const formatParamValue = (value: any): string => {
  if (Array.isArray(value)) {
    return `[${value.join(", ")}]`;
  }
  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value);
  }
  return String(value);
};

/**
 * Get display metrics from result (top metrics to show in table)
 */
const getDisplayMetrics = (metrics: Record<string, any>) => {
  if (!metrics) return {};

  // Priority metrics to display
  const priorityKeys = ["r2", "rmse", "mae", "mse"];
  const display: Record<string, any> = {};

  // Add priority metrics first
  priorityKeys.forEach((key) => {
    if (key in metrics) {
      display[key] = metrics[key];
    }
  });

  // If we have less than 3 metrics, add others
  const otherKeys = Object.keys(metrics).filter(
    (k) => !priorityKeys.includes(k)
  );
  let count = Object.keys(display).length;
  for (const key of otherKeys) {
    if (count >= 3) break;
    display[key] = metrics[key];
    count++;
  }

  return display;
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

<style scoped>
.params-display .param-row,
.params-display .metric-row {
  display: flex;
  align-items: center;
}

.param-key,
.metric-key {
  min-width: 120px;
}
</style>
