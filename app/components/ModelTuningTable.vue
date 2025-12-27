<template>
  <div>
    <h3 class="text-lg font-medium mb-3">
      {{ $t("tuning.modelSelectionAndTuning") }}
    </h3>
    <a-table
      :dataSource="tableData"
      :columns="columns"
      :row-key="getRowKey"
      :pagination="false"
      :expandedRowKeys="expandedKeys"
      @expand="handleExpand"
      class="model-tuning-table"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'model'">
          <span class="font-medium" :class="{ 'pl-8': record.isHistory }">
            {{ record.isHistory ? `└─ ${formatTimestamp(record.createdAt)}` : formatModelName(record.label) }}
          </span>
        </template>
        <template v-else-if="column.key === 'action'">
          <!-- Parent row: Only show Auto Tune and Train buttons -->
          <div v-if="!record.isHistory" class="flex gap-2">
            <a-button
              type="primary"
              size="small"
              :disabled="isTuning"
              @click="handleAutoTune(record.model, record.label)"
              class="inline-flex items-center"
            >
              <span class="i-mdi-tune mr-1" />
              {{ t("tuning.autoTune") }}
            </a-button>
            <a-button
              size="small"
              :disabled="isTuning"
              @click="handleManualTrain(record.model, record.label)"
              class="inline-flex items-center"
            >
              <span class="i-mdi-pencil mr-1" />
              {{ t("tuning.manualTrain") }}
            </a-button>
          </div>
          <!-- Sub-row: Show View Logs button and status tag for each training task -->
          <div v-else class="flex gap-2 items-center">
            <a-button
              v-if="record.taskId"
              size="small"
              @click="handleViewLogs(record.taskId, record.label)"
              class="inline-flex items-center"
            >
              <span class="i-mdi-text-box-outline mr-1" />
              {{ t("tuning.viewLogs") }}
            </a-button>
            <a-tag
              v-if="record.status"
              :color="getStatusColor(record.status)"
            >
              {{ record.status }}
            </a-tag>
          </div>
        </template>
        <template v-else-if="column.key === 'metrics'">
          <div v-if="record.metrics" class="text-sm">
            <div>
              <span class="font-medium">{{ t("metrics.r2") }}:</span>
              {{ formatMetric(record.metrics.r2_test) }}
            </div>
            <div>
              <span class="font-medium">{{ t("metrics.mse") }}:</span>
              {{ formatMetric(record.metrics.mse_test) }}
            </div>
            <div>
              <span class="font-medium">{{ t("metrics.mae") }}:</span>
              {{ formatMetric(record.metrics.mae_test) }}
            </div>
          </div>
          <span v-else class="text-gray-400">{{ t("common.na") }}</span>
        </template>
      </template>
    </a-table>

    <!-- Log Viewer Modal -->
    <a-modal
      v-model:open="logModalVisible"
      :title="t('logs.titleWithModel', { model: currentLogModelName })"
      width="800px"
      :footer="null"
    >
      <LogPanel :logs="currentLogs" />
    </a-modal>

    <!-- ParamGrid Editor Dialog (for auto-tune) -->
    <ParamGridDialog
      v-model="paramGridDialogVisible"
      :model-name="currentEditModel"
      :model-label="currentEditModelLabel"
      :schema="currentModelSchema"
      :initial-values="paramGridValues[currentEditModel]"
      @save="handleSaveAutoTune"
    />

    <!-- Manual Train Dialog -->
    <ManualTrainDialog
      v-model="manualTrainDialogVisible"
      :model-name="currentEditModel"
      :model-label="currentEditModelLabel"
      :schema="currentModelSchema"
      :initial-values="manualTrainValues[currentEditModel]"
      @train="handleSaveManualTrain"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, watch } from "vue";

const { t } = useI18n();

const props = defineProps<{
  availableModels: Array<{ label: string; value: string }>;
  tuningStatus: Record<string, string>;
  tuningTasks: Record<string, string>;
  tuningResults: any[];
  taskLogs: Record<string, any[]>;
  isTuning: boolean;
}>();

const emit = defineEmits<{
  "start-tune": [model: string, paramGrid?: Record<string, any>, trainingType?: string, parentTaskId?: string];
  "view-logs": [taskId: string, modelName: string];
}>();

const logModalVisible = ref(false);
const currentLogTaskId = ref<string>("");
const currentLogModelName = ref<string>("");

// ParamGrid dialog state (for auto-tune)
const paramGridDialogVisible = ref(false);
const manualTrainDialogVisible = ref(false);
const currentEditModel = ref<string>("");
const currentEditModelLabel = ref<string>("");
const modelMetadata = ref<any[]>([]);
const paramGridValues = ref<Record<string, Record<string, any>>>({});
const manualTrainValues = ref<Record<string, Record<string, any>>>({});

// Training history
const trainingHistory = ref<Record<string, any[]>>({});
const expandedKeys = ref<string[]>([]);

const columns = computed(() => [
  { title: t("tuning.model"), key: "model", dataIndex: "model" },
  { title: t("tuning.tuning"), key: "action", width: 350 },
  { title: t("tuning.metrics"), key: "metrics", width: 320 },
]);

// Fetch model metadata on mount
onMounted(async () => {
  try {
    const response = await $fetch("/api/models");
    if (response.success) {
      modelMetadata.value = response.models;
    }
  } catch (error) {
    console.error("Failed to fetch model metadata:", error);
  }
});

// Fetch training history when results change
watch(
  () => props.tuningResults,
  async () => {
    // Fetch history for each model that has results
    for (const result of props.tuningResults) {
      await fetchTrainingHistory(result.model);
    }
  },
  { immediate: true, deep: true }
);

// Get schema for current model being edited
const currentModelSchema = computed(() => {
  const metadata = modelMetadata.value.find(
    (m) => m.name === currentEditModel.value
  );
  return metadata?.paramGridSchema || null;
});

// Fetch training history for a specific model
const fetchTrainingHistory = async (model: string) => {
  try {
    const response = await $fetch(`/api/results/history/${model}`);
    if (response.success && response.results) {
      trainingHistory.value[model] = response.results;
    }
  } catch (error) {
    console.error(`Failed to fetch training history for ${model}:`, error);
  }
};

// Get row key for table
const getRowKey = (record: any) => {
  return record.isHistory ? `${record.model}-${record.taskId}` : record.model;
};

// Handle row expansion
const handleExpand = (expanded: boolean, record: any) => {
  if (expanded) {
    expandedKeys.value.push(record.model);
    // Fetch history when expanding
    fetchTrainingHistory(record.model);
  } else {
    expandedKeys.value = expandedKeys.value.filter((key) => key !== record.model);
  }
};

// Combine all data sources into a single table data structure with expandable rows
const tableData = computed(() => {
  const data: any[] = [];
  
  for (const model of props.availableModels) {
    const status = props.tuningStatus[model.value];
    const taskId = props.tuningTasks[model.value];
    const result = props.tuningResults.find((r) => r.model === model.value);

    // Parent row
    const parentRow = {
      model: model.value,
      label: model.label,
      status: status,
      taskId: taskId,
      metrics: result
        ? {
            r2_test: result.r2_test,
            mse_test: result.mse_test,
            mae_test: result.mae_test,
          }
        : null,
      isHistory: false,
    };
    
    data.push(parentRow);

    // Add history rows if expanded
    if (expandedKeys.value.includes(model.value)) {
      // First, add the current active task if it exists
      if (status && taskId) {
        data.push({
          model: model.value,
          label: model.label,
          taskId: taskId,
          status: status,
          metrics: result
            ? {
                r2_test: result.r2_test,
                mse_test: result.mse_test,
                mae_test: result.mae_test,
              }
            : null,
          params: result?.params,
          trainingType: result?.trainingType || "auto",
          createdAt: result?.createdAt || new Date(),
          isHistory: true,
          isCurrent: true, // Mark this as the current active task
        });
      }
      
      // Then add historical tasks
      const history = trainingHistory.value[model.value] || [];
      for (const historyItem of history) {
        // Skip if this is the current task (already added above)
        if (historyItem.taskId === taskId) continue;
        
        data.push({
          model: model.value,
          label: model.label,
          taskId: historyItem.taskId,
          status: historyItem.status || "completed", // Use status from API, fallback to completed
          metrics: {
            r2_test: historyItem.r2_test,
            mse_test: historyItem.mse_test,
            mae_test: historyItem.mae_test,
          },
          params: historyItem.params,
          trainingType: historyItem.trainingType || "auto",
          createdAt: historyItem.createdAt,
          isHistory: true,
        });
      }
    }
  }

  return data;
});

const formatModelName = (name: string) => {
  return name.replace(/_/g, " ");
};

const formatTimestamp = (timestamp: any) => {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  return date.toLocaleString();
};

const formatMetric = (value: string | number) => {
  if (!value) return t("common.na");
  const num = typeof value === "string" ? parseFloat(value) : value;
  return num.toFixed(4);
};

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    completed: "green",
    running: "blue",
    pending: "orange",
    failed: "red",
  };
  return colors[status?.toLowerCase()] || "default";
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
  emit("view-logs", taskId, modelName);
};

// Handle auto tune (with param grid editing)
const handleAutoTune = (modelName: string, modelLabel: string) => {
  currentEditModel.value = modelName;
  currentEditModelLabel.value = modelLabel;
  paramGridDialogVisible.value = true;
};

// Handle manual train
const handleManualTrain = (modelName: string, modelLabel: string) => {
  currentEditModel.value = modelName;
  currentEditModelLabel.value = modelLabel;
  manualTrainDialogVisible.value = true;
};

// Handle save auto tune (with param grid)
const handleSaveAutoTune = (values: Record<string, any>) => {
  paramGridValues.value[currentEditModel.value] = values;
  // Start auto-tune with param grid
  emit("start-tune", currentEditModel.value, values, "auto");
};

// Handle save manual train
const handleSaveManualTrain = (values: Record<string, any>) => {
  manualTrainValues.value[currentEditModel.value] = values;
  // Find the parent task ID (the most recent auto-tune task for this model)
  const parentTaskId = props.tuningTasks[currentEditModel.value] || null;
  // Start manual train with single values
  emit("start-tune", currentEditModel.value, values, "manual", parentTaskId);
};
</script>

<style scoped>
.model-tuning-table :deep(.ant-table-row:hover) {
  background-color: #f5f5f5;
}

.model-tuning-table :deep(.ant-table-expanded-row) {
  background-color: #fafafa;
}

.model-tuning-table :deep(.ant-table-expanded-row > td) {
  border-bottom: 1px solid #e8e8e8;
}
</style>

