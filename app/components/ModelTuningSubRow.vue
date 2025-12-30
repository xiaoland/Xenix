<template>
  <tr class="bg-gray-50 border-b">
    <!-- Select Column -->
    <td class="px-4 py-2 text-center">
      <a-radio
        :checked="selectedTaskId === taskId"
        @click="$emit('update:selectedTaskId', taskId)"
      />
    </td>
    
    <!-- Model Name / Timestamp Column -->
    <td class="px-4 py-2">
      <span class="font-medium pl-2">
        {{ formatTimestamp(task?.createdAt) }}
      </span>
    </td>
    
    <!-- Tune Type Column -->
    <td class="px-4 py-2">
      <div class="text-sm">
        <div class="font-medium mb-1">
          <a-tag v-if="taskType === 'auto-tune'" color="blue">
            {{ t("tuning.autoTune") }}
          </a-tag>
          <a-tag v-else-if="taskType === 'tune'" color="green">
            {{ t("tuning.manualTune") }}
          </a-tag>
        </div>
        <div v-if="taskParams" class="text-xs text-gray-600">
          <div
            v-for="(value, key) in taskParams"
            :key="key"
            class="truncate"
          >
            <span class="font-medium">{{ key }}:</span>
            {{ formatParamValue(value) }}
          </div>
        </div>
      </div>
    </td>
    
    <!-- Action Column -->
    <td class="px-4 py-2">
      <div class="flex gap-2 items-center">
        <a-button
          size="small"
          @click="handleViewLogs"
          class="inline-flex items-center"
        >
          <span class="i-mdi-text-box-outline mr-1" />
          {{ t("tuning.viewLogs") }}
        </a-button>
        <a-tag v-if="task?.status" :color="getStatusColor(task.status)">
          {{ task.status }}
        </a-tag>
      </div>
    </td>
    
    <!-- Metrics Column -->
    <td class="px-4 py-2">
      <ModelAutoMetrics :metrics="taskMetrics" />
    </td>
  </tr>

  <!-- Log Modal -->
  <teleport to="body">
    <a-modal
      v-model:open="logModalVisible"
      :title="t('logs.titleWithTask', { taskId })"
      width="800px"
      :footer="null"
    >
      <LogPanel :logs="taskLogs" />
    </a-modal>
  </teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import { TaskService } from "~/services";
import { useFormatters } from "~/composables/useFormatters";
import type { TaskInfo, TuningMetrics } from "~/types";

const { t } = useI18n();
const { formatTimestamp, formatMetric, getStatusColor } = useFormatters();

const props = defineProps<{
  taskId: number;
  selectedTaskId: number | null;
}>();

const emit = defineEmits<{
  "update:selectedTaskId": [taskId: number | null];
}>();

// Local state
const task = ref<TaskInfo | null>(null);
const taskLogs = ref<any[]>([]);
const logModalVisible = ref(false);

// Computed properties
const taskType = computed(() => {
  return task.value?.parameter?.type || task.value?.type || 'unknown';
});

const taskParams = computed(() => {
  const result = task.value?.result;
  return result?.params || null;
});

const taskMetrics = computed((): TuningMetrics | null => {
  const result = task.value?.result;
  if (!result?.metrics) return null;
  return result.metrics;
});

// Fetch task data
const fetchTask = async () => {
  try {
    const response = await TaskService.fetchStatus(props.taskId);
    if (response.task) {
      task.value = response.task;
    }
  } catch (error) {
    console.error(`Failed to fetch task ${props.taskId}:`, error);
  }
};

// Fetch task logs
const fetchTaskLogs = async () => {
  try {
    const response = await TaskService.fetchLogs(props.taskId);
    if (response.success && response.logs) {
      taskLogs.value = response.logs;
    }
  } catch (error) {
    console.error(`Failed to fetch logs for task ${props.taskId}:`, error);
  }
};

// Event handlers
const handleViewLogs = () => {
  logModalVisible.value = true;
  fetchTaskLogs();
};

const formatParamValue = (value: any): string => {
  if (Array.isArray(value)) {
    return `[${value.join(", ")}]`;
  }
  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value);
  }
  return String(value);
};

// Poll for task updates if status is not completed or failed
const pollTask = () => {
  if (task.value && (task.value.status === 'pending' || task.value.status === 'running')) {
    setTimeout(() => {
      fetchTask().then(() => {
        if (task.value && (task.value.status === 'pending' || task.value.status === 'running')) {
          pollTask();
        }
      });
    }, 3000); // Poll every 3 seconds
  }
};

// Watch for taskId changes
watch(
  () => props.taskId,
  () => {
    fetchTask().then(() => {
      pollTask();
    });
  },
  { immediate: true }
);

// Initialize
onMounted(() => {
  fetchTask().then(() => {
    pollTask();
  });
});
</script>
