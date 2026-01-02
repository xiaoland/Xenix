<template>
  <div class="mt-6">
    <h3 class="text-lg font-medium mb-3">{{ title || t("logs.title") }}</h3>
    <LogPanel :logs="taskLogs" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import LogPanel from "./LogPanel.vue";
import { TaskService } from "~/services/taskService";
import type { TaskLog } from "~/types";

const { t } = useI18n();

const props = defineProps<{
  taskId: number;
  title?: string;
}>();

const taskStatus = ref<string>("");
const taskLogs = ref<TaskLog[]>([]);
let pollingInterval: NodeJS.Timeout | null = null;

const fetchTaskStatus = async () => {
  try {
    const res = await TaskService.fetchStatus(props.taskId);
    taskStatus.value = res.task.status;
  } catch (e) {
    console.error("Failed to fetch task status", e);
  }
};

const fetchLogs = async () => {
  try {
    const res = await TaskService.fetchLogs(props.taskId);
    if (res.success) {
      taskLogs.value = res.logs;
    }
  } catch (e) {
    console.error("Failed to fetch logs", e);
  }
};

const startPolling = () => {
  if (pollingInterval) return; // Already polling
  pollingInterval = setInterval(async () => {
    await fetchTaskStatus();
    if (["running", "pending"].includes(taskStatus.value)) {
      await fetchLogs();
    } else {
      stopPolling();
      if (["completed", "failed"].includes(taskStatus.value)) {
        await fetchLogs();
      }
    }
  }, 3000);
};

const stopPolling = () => {
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
};

onMounted(async () => {
  await fetchTaskStatus();
  await fetchLogs();
  if (["running", "pending"].includes(taskStatus.value)) {
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
    taskStatus.value = "";
    taskLogs.value = [];
    stopPolling();
    await fetchTaskStatus();
    await fetchLogs();
    if (["running", "pending"].includes(taskStatus.value)) {
      startPolling();
    }
  }
);

// Watch for taskStatus changes
watch(taskStatus, async (newStatus) => {
  if (["completed", "failed"].includes(newStatus)) {
    stopPolling();
    await fetchLogs();
  }
});
</script>
