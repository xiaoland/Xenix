<template>
  <div class="space-y-4">
    <!-- Task Status -->
    <a-alert
      v-if="task"
      :message="statusMessage"
      :type="statusType"
      show-icon
      closable
    />

    <!-- Loading State -->
    <div
      v-if="task && (task.status === 'pending' || task.status === 'running')"
      class="text-center py-8"
    >
      <a-spin size="large" />
      <p class="mt-4 text-gray-600">
        {{ $t("ml.prediction.processing") }}
      </p>
    </div>

    <!-- Results -->
    <div v-else-if="task && task.status === 'completed'">
      <!-- Download Button (for file mode) -->
      <div v-if="(task.result as any)?.predictedDataPath" class="mb-4">
        <a-button
          type="primary"
          class="inline-flex items-center"
          :loading="downloading"
          @click="handleDownload"
        >
          <span class="i-mdi-download mr-2"></span>
          {{ $t("ml.prediction.downloadResults") }}
        </a-button>
      </div>

      <!-- Inline Results (for inline mode) -->
      <div
        v-if="(task.result as any)?.predictedData"
        class="bg-white rounded-lg border p-4"
      >
        <h4 class="text-md font-medium mb-3">
          {{ $t("ml.prediction.results") }}
        </h4>
        <a-table
          :columns="resultColumns"
          :data-source="formattedResults"
          :pagination="false"
          bordered
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'prediction'">
              <span class="font-semibold text-blue-600">{{
                record.prediction
              }}</span>
            </template>
          </template>
        </a-table>
      </div>

      <!-- Summary Stats -->
      <div
        v-if="(task.result as any)?.predictedData"
        class="bg-gray-50 rounded-lg p-4 mt-4"
      >
        <h4 class="text-md font-medium mb-2">Summary</h4>
        <div class="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span class="text-gray-600">Total Predictions:</span>
            <span class="ml-2 font-medium">{{
              (task.result as any).predictedData.length
            }}</span>
          </div>
          <div v-if="(task.result as any).predictedData.length > 0">
            <span class="text-gray-600">Avg Prediction:</span>
            <span class="ml-2 font-medium">{{ avgPrediction }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="task && task.status === 'failed'" class="text-center py-8">
      <span
        class="i-mdi-alert-circle text-6xl text-red-500 inline-block mb-4"
      ></span>
      <h3 class="text-xl font-semibold text-red-600 mb-2">Prediction Failed</h3>
      <p class="text-gray-600">
        {{ task.error || "An unknown error occurred" }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { message } from "ant-design-vue";

import { computed, onMounted, onUnmounted, ref, watch } from "vue";

import type { PredictTaskResult, Task } from "@xenix/shared";

import { client } from "../../../api/client";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const props = defineProps<{
  taskId: number;
  workItemId: number;
}>();

// State
const task = ref<Task | null>(null);
const downloading = ref(false);
const loading = ref(false);

// Polling interval
let pollInterval: number | null = null;

/**
 * Fetch task status and manage polling
 */
const fetchAndPollTask = async () => {
  stopPolling();
  task.value = null;
  await fetchTaskStatus();
  if (
    task.value &&
    ((task.value as Task).status === "pending" ||
      (task.value as Task).status === "running")
  ) {
    startPolling();
  }
};

// Watch for taskId changes
watch(
  () => props.taskId,
  () => {
    fetchAndPollTask();
  },
);

// Computed
const statusMessage = computed(() => {
  if (!task.value) return "";

  switch (task.value.status) {
    case "pending":
      return "Prediction task queued";
    case "running":
      return "Generating predictions...";
    case "completed":
      return "Prediction completed successfully!";
    case "failed":
      return `Prediction failed: ${task.value.error || "Unknown error"}`;
    default:
      return "";
  }
});

const statusType = computed(() => {
  if (!task.value) return "info";

  switch (task.value.status) {
    case "completed":
      return "success";
    case "failed":
      return "error";
    case "running":
      return "info";
    default:
      return "info";
  }
});

const resultColumns = computed(() => {
  const predictResult = task.value?.result as any;
  if (
    !predictResult?.predictedData ||
    predictResult.predictedData.length === 0
  ) {
    return [];
  }

  const firstRow = predictResult.predictedData[0];
  const cols: any[] = Object.keys(firstRow)
    .filter((key) => key !== "prediction")
    .map((key) => ({
      title: key,
      dataIndex: key,
      key,
    }));

  return cols;
});

const formattedResults = computed(() => {
  const predictResult = task.value?.result as any;
  if (!predictResult?.predictedData) return [];
  return predictResult.predictedData.map((pred: any, index: number) => ({
    ...pred,
    key: index,
  }));
});

const avgPrediction = computed(() => {
  const predictResult = task.value?.result as any;
  if (
    !predictResult?.predictedData ||
    predictResult.predictedData.length === 0
  ) {
    return "-";
  }

  const predictions = predictResult.predictedData.map((p: any) => p.prediction);
  const sum = predictions.reduce((acc: number, val: number) => acc + val, 0);
  const avg = sum / predictions.length;
  return avg.toFixed(4);
});

/**
 * Fetch task status
 */
const fetchTaskStatus = async () => {
  loading.value = true;
  try {
    const response = await client.tasks[":id"].$get({
      param: { id: String(props.taskId) },
    });
    if (!response.ok) throw new Error("Failed to fetch task");
    const data = await response.json();
    task.value = data as any;
  } catch (error) {
    console.error("Failed to fetch task:", error);
  } finally {
    loading.value = false;
  }
};

/**
 * Start polling for task updates
 */
const startPolling = () => {
  if (pollInterval) return;
  pollInterval = window.setInterval(() => {
    if (
      task.value &&
      ((task.value as Task).status === "pending" ||
        (task.value as Task).status === "running")
    ) {
      fetchTaskStatus();
    } else {
      stopPolling();
    }
  }, 2000);
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
 * Download or open result file
 *
 * The backend transforms paths based on deployment storage type:
 * - Local storage: Absolute file path (e.g., /tmp/ml-backend/tasks/123/predictions.xlsx)
 * - OSS storage: Presigned HTTP URL (e.g., https://...)
 */
const handleDownload = async () => {
  const predictResult = task.value?.result as any;
  if (!predictResult?.predictedDataPath) return;

  downloading.value = true;
  try {
    const filePath = predictResult.predictedDataPath;

    // Check if it's an HTTP URL (OSS storage)
    if (filePath.startsWith("http://") || filePath.startsWith("https://")) {
      // OSS storage: Download from presigned URL
      const link = document.createElement("a");
      link.href = filePath;
      link.download = filePath.split("/").pop() || "predictions.xlsx";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      message.success("Download started");
    } else {
      // Local storage: Copy path to clipboard since browsers can't open local files
      await navigator.clipboard.writeText(filePath);
      message.success(t("prediction.filePathCopied"));
    }
  } catch (error: any) {
    console.error("Download/open failed:", error);
    message.error(error.message || "Failed to open file");
  } finally {
    downloading.value = false;
  }
};

// Lifecycle
onMounted(async () => {
  await fetchAndPollTask();
});

onUnmounted(() => {
  stopPolling();
});
</script>
