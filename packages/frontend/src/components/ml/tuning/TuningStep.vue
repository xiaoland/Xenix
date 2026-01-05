<template>
  <div class="space-y-6">
    <h2 class="text-2xl font-semibold mb-4">Model Tuning</h2>

    <a-alert
      message="Train machine learning models"
      description="Select models and configure hyperparameters to train on your dataset. Select a completed task to continue to predictions."
      type="info"
      show-icon
      class="mb-4"
    />

    <!-- Model Selection -->
    <div class="bg-white rounded-lg border p-4 mb-4">
      <h3 class="text-lg font-medium mb-3">Select Models to Train</h3>
      <a-select
        v-model:value="selectedModels"
        mode="multiple"
        placeholder="Select models to train"
        style="width: 100%"
        :options="availableModels"
        class="mb-3"
      />
      
      <div class="flex gap-2">
        <a-button
          type="primary"
          :loading="isTraining"
          :disabled="selectedModels.length === 0"
          @click="handleStartAutoTune"
        >
          <span class="i-mdi-auto-fix mr-1"></span>
          Start Auto-Tune
        </a-button>
        <a-button
          :disabled="tasks.length === 0"
          danger
          @click="handleClearFailedTasks"
        >
          <span class="i-mdi-delete-outline mr-1"></span>
          Clear Failed Tasks
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
            <span class="font-medium">{{ formatModelName(record.parameter?.model) }}</span>
          </template>
          
          <template v-else-if="column.key === 'status'">
            <a-tag :color="getStatusColor(record.status)">
              {{ record.status }}
            </a-tag>
          </template>
          
          <template v-else-if="column.key === 'metrics'">
            <div v-if="record.status === 'completed' && record.result?.params" class="text-sm">
              <div v-for="(value, key) in getDisplayMetrics(record.result)" :key="key">
                <span class="text-gray-600">{{ key }}:</span>
                <span class="ml-1 font-medium">{{ formatMetric(value) }}</span>
              </div>
            </div>
            <span v-else-if="record.status === 'failed'" class="text-red-500 text-sm">
              {{ record.error || 'Training failed' }}
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

      <div v-if="tasks.length === 0 && !loading" class="text-center py-8 text-gray-500">
        No training tasks yet. Select models and start training.
      </div>
    </div>

    <!-- Navigation -->
    <div class="flex justify-between">
      <a-button @click="emit('back')">
        Back to Prepare
      </a-button>
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
import { ref, onMounted, onUnmounted } from 'vue';
import { message } from 'ant-design-vue';
import { TuneService, TaskService, WorkItemService } from '../../../services';
import { AVAILABLE_MODELS } from '../../../constants/models';
import type { TaskInfo } from '@xenix/shared';

const props = defineProps<{
  workItemId: number;
  datasetId: string;
  featureColumns: string[];
  targetColumn: string;
}>();

const emit = defineEmits<{
  continue: [data: { model: string; parameters: Record<string, any>; taskId: number }];
  back: [];
}>();

// State
const selectedModels = ref<string[]>([]);
const tasks = ref<TaskInfo[]>([]);
const selectedTaskId = ref<number | null>(null);
const loading = ref(false);
const isTraining = ref(false);

// Available models
const availableModels = AVAILABLE_MODELS.map(m => ({
  label: m.label,
  value: m.value,
}));

// Table columns
const columns = [
  { title: 'Model', key: 'model', width: 200 },
  { title: 'Status', key: 'status', width: 120 },
  { title: 'Metrics / Error', key: 'metrics' },
  { title: 'Action', key: 'action', width: 100 },
];

// Polling interval
let pollInterval: number | null = null;

/**
 * Fetch tuning tasks for the work item
 */
const fetchTasks = async () => {
  loading.value = true;
  try {
    const response = await TaskService.fetchByWorkItemId(props.workItemId, ['auto-tune', 'manual-tune']);
    tasks.value = response.tasks || [];
  } catch (error) {
    console.error('Failed to fetch tasks:', error);
  } finally {
    loading.value = false;
  }
};

/**
 * Start auto-tune for selected models
 */
const handleStartAutoTune = async () => {
  isTraining.value = true;
  try {
    // Start training for each selected model
    for (const model of selectedModels.value) {
      await TuneService.startAutoTune({
        datasetId: props.datasetId,
        features: props.featureColumns,
        target: props.targetColumn,
        model,
        workItemId: props.workItemId,
      });
    }
    message.success(`Started training for ${selectedModels.value.length} model(s)`);
    selectedModels.value = [];
    await fetchTasks();
    startPolling();
  } catch (error: any) {
    console.error('Failed to start training:', error);
    message.error(error.message || 'Failed to start training');
  } finally {
    isTraining.value = false;
  }
};

/**
 * Clear all failed tasks
 */
const handleClearFailedTasks = async () => {
  try {
    await TaskService.deleteFailedTasks(props.workItemId);
    message.success('Failed tasks cleared');
    await fetchTasks();
  } catch (error: any) {
    console.error('Failed to clear tasks:', error);
    message.error(error.message || 'Failed to clear tasks');
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
    const response = await TaskService.fetchStatus(selectedTaskId.value);
    if (response.task) {
      emit('continue', {
        model: response.task.parameter?.model || '',
        parameters: response.task.result?.params || {},
        taskId: selectedTaskId.value,
      });
    }
  } catch (error: any) {
    console.error('Failed to fetch task:', error);
    message.error(error.message || 'Failed to fetch task details');
  }
};

/**
 * Start polling for task updates
 */
const startPolling = () => {
  if (pollInterval) return;
  pollInterval = window.setInterval(() => {
    const hasRunningTasks = tasks.value.some(t => 
      t.status === 'pending' || t.status === 'running'
    );
    if (hasRunningTasks) {
      fetchTasks();
    } else {
      stopPolling();
    }
  }, 3000);
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
    case 'completed': return 'success';
    case 'failed': return 'error';
    case 'running': return 'processing';
    case 'pending': return 'default';
    default: return 'default';
  }
};

/**
 * Format model name
 */
const formatModelName = (modelValue?: string) => {
  if (!modelValue) return '-';
  const model = AVAILABLE_MODELS.find(m => m.value === modelValue);
  return model ? model.label : modelValue;
};

/**
 * Format metric value
 */
const formatMetric = (value: any) => {
  if (typeof value === 'number') {
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
  if (result.score !== undefined) metrics['Score'] = result.score;
  if (result.params) {
    const paramCount = Object.keys(result.params).length;
    metrics['Parameters'] = `${paramCount} params`;
  }
  return metrics;
};

// Lifecycle
onMounted(async () => {
  await fetchTasks();
  const hasRunningTasks = tasks.value.some(t => 
    t.status === 'pending' || t.status === 'running'
  );
  if (hasRunningTasks) {
    startPolling();
  }
});

onUnmounted(() => {
  stopPolling();
});
</script>
