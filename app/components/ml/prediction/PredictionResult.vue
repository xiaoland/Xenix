<template>
  <div class="space-y-4">
    <!-- Task Status Alert -->
    <a-alert :message="statusMessage" :type="statusType" show-icon />

    <!-- Task Logs -->
    <TaskLogViewer v-if="taskId" :task-id="taskId" :title="t('logs.title')" />

    <!-- Results for Completed Tasks -->
    <div v-if="task && task.status === 'completed'" class="mt-6">
      <h3 class="text-lg font-medium mb-4">{{ t("prediction.results") }}</h3>

      <!-- Download Results -->
      <div v-if="task.result?.outputPath" class="">
        <a-button
          type="primary"
          class="inline-flex items-center justify-center w-full"
          @click="downloadResults"
        >
          <span class="i-mdi-download mr-2" />
          {{ t("prediction.downloadResult") }}
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import { TaskService } from "~/services";
import type { TaskInfo } from "~/types";
import TaskLogViewer from "~/components/obsrv/TaskLogViewer.vue";

const { t } = useI18n();

const props = defineProps<{
  taskId: number;
  inputData?: Record<string, any>[];
}>();

const task = ref<TaskInfo | null>(null);
let pollingInterval: NodeJS.Timeout | null = null;

// Computed properties
const statusMessage = computed(() => {
  if (!task.value) return t("prediction.loading");

  switch (task.value.status) {
    case "pending":
      return t("prediction.taskQueued");
    case "running":
      return t("prediction.generating");
    case "completed":
      return t("prediction.completed");
    case "failed":
      return t("prediction.failed", {
        error: task.value.error || t("common.unknownError"),
      });
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
    default:
      return "info";
  }
});

// Methods
const fetchTask = async () => {
  try {
    const response = await TaskService.fetchStatus(props.taskId);
    task.value = response.task;
  } catch (error) {
    console.error("Failed to fetch task:", error);
  }
};

const startPolling = () => {
  if (pollingInterval) return;
  pollingInterval = setInterval(async () => {
    await fetchTask();
    if (task.value && !["pending", "running"].includes(task.value.status)) {
      stopPolling();
    }
  }, 5000);
};

const stopPolling = () => {
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
};

const downloadResults = () => {
  const downloadUrl = `/api/download/${props.taskId}`;
  const link = document.createElement("a");
  link.href = downloadUrl;
  link.download = "";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

// Lifecycle
onMounted(async () => {
  await fetchTask();
  if (task.value && ["pending", "running"].includes(task.value.status)) {
    startPolling();
  }
});

onUnmounted(() => {
  stopPolling();
});

// Watch for taskId changes
watch(
  () => props.taskId,
  async (newTaskId) => {
    if (!newTaskId) return;
    task.value = null;
    stopPolling();
    await fetchTask();
    if (task.value && ["pending", "running"].includes(task.value.status)) {
      startPolling();
    }
  }
);
</script>
