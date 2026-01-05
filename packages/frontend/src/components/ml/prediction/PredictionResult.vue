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
    <div v-if="task && (task.status === 'pending' || task.status === 'running')" class="text-center py-8">
      <a-spin size="large" />
      <p class="mt-4 text-gray-600">Processing prediction...</p>
    </div>

    <!-- Results -->
    <div v-else-if="task && task.status === 'completed'">
      <!-- Download Button (for file mode) -->
      <div v-if="task.result?.outputFile" class="mb-4">
        <a-button type="primary" @click="handleDownload" :loading="downloading">
          <span class="i-mdi-download mr-2"></span>
          Download Results
        </a-button>
      </div>

      <!-- Inline Results (for inline mode) -->
      <div v-if="task.result?.predictions" class="bg-white rounded-lg border p-4">
        <h4 class="text-md font-medium mb-3">Prediction Results</h4>
        <a-table
          :columns="resultColumns"
          :data-source="formattedResults"
          :pagination="false"
          bordered
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'prediction'">
              <span class="font-semibold text-blue-600">{{ record.prediction }}</span>
            </template>
          </template>
        </a-table>
      </div>

      <!-- Summary Stats -->
      <div v-if="task.result?.predictions" class="bg-gray-50 rounded-lg p-4 mt-4">
        <h4 class="text-md font-medium mb-2">Summary</h4>
        <div class="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span class="text-gray-600">Total Predictions:</span>
            <span class="ml-2 font-medium">{{ task.result.predictions.length }}</span>
          </div>
          <div v-if="task.result.predictions.length > 0">
            <span class="text-gray-600">Avg Prediction:</span>
            <span class="ml-2 font-medium">{{ avgPrediction }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="task && task.status === 'failed'" class="text-center py-8">
      <span class="i-mdi-alert-circle text-6xl text-red-500 inline-block mb-4"></span>
      <h3 class="text-xl font-semibold text-red-600 mb-2">Prediction Failed</h3>
      <p class="text-gray-600">{{ task.error || 'An unknown error occurred' }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { message } from 'ant-design-vue';
import { TaskService } from '../../../services';
import type { TaskInfo } from '@xenix/shared';

const props = defineProps<{
  taskId: number;
  workItemId: number;
}>();

// State
const task = ref<TaskInfo | null>(null);
const downloading = ref(false);
const loading = ref(false);

// Polling interval
let pollInterval: number | null = null;

// Computed
const statusMessage = computed(() => {
  if (!task.value) return '';
  
  switch (task.value.status) {
    case 'pending':
      return 'Prediction task queued';
    case 'running':
      return 'Generating predictions...';
    case 'completed':
      return 'Prediction completed successfully!';
    case 'failed':
      return `Prediction failed: ${task.value.error || 'Unknown error'}`;
    default:
      return '';
  }
});

const statusType = computed(() => {
  if (!task.value) return 'info';
  
  switch (task.value.status) {
    case 'completed':
      return 'success';
    case 'failed':
      return 'error';
    case 'running':
      return 'info';
    default:
      return 'info';
  }
});

const resultColumns = computed(() => {
  if (!task.value?.result?.predictions || task.value.result.predictions.length === 0) {
    return [];
  }

  const firstRow = task.value.result.predictions[0];
  const cols: any[] = Object.keys(firstRow)
    .filter(key => key !== 'prediction')
    .map(key => ({
      title: key,
      dataIndex: key,
      key,
    }));
  
  cols.push({
    title: 'Prediction',
    dataIndex: 'prediction',
    key: 'prediction',
  });
  
  return cols;
});

const formattedResults = computed(() => {
  if (!task.value?.result?.predictions) return [];
  return task.value.result.predictions.map((pred: any, index: number) => ({
    ...pred,
    key: index,
  }));
});

const avgPrediction = computed(() => {
  if (!task.value?.result?.predictions || task.value.result.predictions.length === 0) {
    return '-';
  }
  
  const predictions = task.value.result.predictions.map((p: any) => p.prediction);
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
    const response = await TaskService.fetchStatus(props.taskId);
    task.value = response.task;
  } catch (error) {
    console.error('Failed to fetch task:', error);
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
    if (task.value && (task.value.status === 'pending' || task.value.status === 'running')) {
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
 * Download result file
 */
const handleDownload = async () => {
  if (!task.value?.result?.outputFile) return;
  
  downloading.value = true;
  try {
    // Create download link
    const link = document.createElement('a');
    link.href = `/api/download/${task.value.id}`;
    link.download = task.value.result.outputFile;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    message.success('Download started');
  } catch (error: any) {
    console.error('Download failed:', error);
    message.error(error.message || 'Failed to download file');
  } finally {
    downloading.value = false;
  }
};

// Lifecycle
onMounted(async () => {
  await fetchTaskStatus();
  if (task.value && (task.value.status === 'pending' || task.value.status === 'running')) {
    startPolling();
  }
});

onUnmounted(() => {
  stopPolling();
});
</script>
