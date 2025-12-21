<template>
  <div>
    <h3 class="text-lg font-medium mb-3">Model Selection and Tuning</h3>
    <a-table
      :dataSource="tableData"
      :columns="columns"
      :row-key="(record) => record.model"
      :row-selection="rowSelection"
      :pagination="false"
      class="model-tuning-table"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'model'">
          <span class="font-medium">{{ formatModelName(record.label) }}</span>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button
            v-if="!record.status || record.status === 'pending'"
            type="primary"
            size="small"
            :disabled="!isModelSelected(record.model) || isTuning"
            @click="handleStartTune(record.model)"
          >
            <i class="i-mdi-tune mr-1"></i>
            Start Tune
          </a-button>
          <a-button
            v-else
            size="small"
            @click="handleViewLogs(record.taskId, record.label)"
          >
            <i class="i-mdi-text-box-outline mr-1"></i>
            View Logs
          </a-button>
          <a-tag
            v-if="record.status && record.status !== 'pending'"
            :color="getStatusColor(record.status)"
            class="ml-2"
          >
            {{ record.status }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'metrics'">
          <div v-if="record.metrics" class="text-sm">
            <div><span class="font-medium">R²:</span> {{ formatMetric(record.metrics.r2_test) }}</div>
            <div><span class="font-medium">MSE:</span> {{ formatMetric(record.metrics.mse_test) }}</div>
            <div><span class="font-medium">MAE:</span> {{ formatMetric(record.metrics.mae_test) }}</div>
          </div>
          <span v-else class="text-gray-400">-</span>
        </template>
      </template>
    </a-table>

    <!-- Log Viewer Modal -->
    <a-modal
      v-model:open="logModalVisible"
      :title="`Logs - ${currentLogModelName}`"
      width="800px"
      :footer="null"
    >
      <LogPanel :logs="currentLogs" />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

const props = defineProps<{
  availableModels: Array<{ label: string; value: string }>;
  selectedModels: string[];
  tuningStatus: Record<string, string>;
  tuningTasks: Record<string, string>;
  tuningResults: any[];
  taskLogs: Record<string, any[]>;
  isTuning: boolean;
}>();

const emit = defineEmits<{
  'update:selectedModels': [models: string[]];
  'start-tune': [model: string];
  'view-logs': [taskId: string, modelName: string];
}>();

const logModalVisible = ref(false);
const currentLogTaskId = ref<string>('');
const currentLogModelName = ref<string>('');

const columns = [
  { title: 'Model', key: 'model', dataIndex: 'model' },
  { title: 'Start Tune / View Logs', key: 'action', width: 200 },
  { title: 'Metrics', key: 'metrics', width: 200 },
];

// Combine all data sources into a single table data structure
const tableData = computed(() => {
  return props.availableModels.map(model => {
    const status = props.tuningStatus[model.value];
    const taskId = props.tuningTasks[model.value];
    const result = props.tuningResults.find(r => r.model === model.value);
    
    return {
      model: model.value,
      label: model.label,
      status: status,
      taskId: taskId,
      metrics: result ? {
        r2_test: result.r2_test,
        mse_test: result.mse_test,
        mae_test: result.mae_test,
      } : null,
    };
  });
});

const rowSelection = computed(() => ({
  selectedRowKeys: props.selectedModels,
  onChange: (selectedRowKeys: string[]) => {
    emit('update:selectedModels', selectedRowKeys);
  },
}));

const isModelSelected = (model: string) => {
  return props.selectedModels.includes(model);
};

const formatModelName = (name: string) => {
  return name.replace(/_/g, ' ');
};

const formatMetric = (value: string | number) => {
  if (!value) return 'N/A';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  return num.toFixed(4);
};

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    completed: 'green',
    running: 'blue',
    pending: 'orange',
    failed: 'red',
  };
  return colors[status?.toLowerCase()] || 'default';
};

const currentLogs = computed(() => {
  if (!currentLogTaskId.value) return [];
  return props.taskLogs[currentLogTaskId.value] || [];
});

// Handle view logs event
const handleViewLogs = (taskId: string, modelName: string) => {
  currentLogTaskId.value = taskId;
  currentLogModelName.value = modelName;
  logModalVisible.value = true;
  emit('view-logs', taskId, modelName);
};

const handleStartTune = (model: string) => {
  emit('start-tune', model);
};
</script>

<style scoped>
.model-tuning-table :deep(.ant-table-row) {
  cursor: pointer;
}

.model-tuning-table :deep(.ant-table-row:hover) {
  background-color: #f5f5f5;
}

.model-tuning-table :deep(.ant-table-row-selected) {
  background-color: #e6f7ff;
}
</style>
