<template>
  <div class="mt-6">
    <h3 class="text-lg font-medium mb-3">{{ title || t("logs.title") }}</h3>
    <LogPanel :logs="taskLogs" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { useI18n } from "vue-i18n";
import LogPanel from "./LogPanel.vue";
import { useTaskPolling } from "~/composables/useTaskPolling";

const { t } = useI18n();
const { fetchTaskLogs, pollTaskLogs } = useTaskPolling();

const props = defineProps<{
  taskId: number;
  title?: string;
}>();

const taskLogs = ref<any[]>([]);
let pollingInterval: number | null = null;

// Fetch logs initially and start polling
const startPolling = () => {
  fetchTaskLogs(props.taskId).then(() => {
    taskLogs.value = useTaskPolling().taskLogs.value[props.taskId] || [];
  });
  pollingInterval = window.setInterval(() => {
    pollTaskLogs(props.taskId);
    taskLogs.value = useTaskPolling().taskLogs.value[props.taskId] || [];
  }, 3000);
};

// Stop polling
const stopPolling = () => {
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
};

onMounted(() => {
  startPolling();
});

onUnmounted(() => {
  stopPolling();
});
</script>
