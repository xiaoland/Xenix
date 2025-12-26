<template>
  <div>
    <h3 class="text-lg font-medium mb-3">
      {{ $t("tuning.modelSelectionAndTuning") }}
    </h3>
    <a-table
      :dataSource="tableData"
      :columns="columns"
      :row-key="(record) => record.model"
      :pagination="false"
      class="model-tuning-table"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'model'">
          <span class="font-medium">{{ formatModelName(record.label) }}</span>
        </template>
        <template v-else-if="column.key === 'paramGrid'">
          <a-button
            size="small"
            @click="handleEditParamGrid(record.model, record.label)"
            class="inline-flex items-center"
          >
            <span class="i-mdi-tune-variant mr-1" />
            {{ t("tuning.paramGrid.editButton") }}
          </a-button>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button
            v-if="!record.status || record.status === 'pending'"
            type="primary"
            size="small"
            :disabled="isTuning"
            @click="handleStartTune(record.model)"
            class="inline-flex items-center"
          >
            <span class="i-mdi-tune mr-1" />
            {{ t("tuning.startTune") }}
          </a-button>
          <div v-else class="flex items-center gap-2">
            <a-button
              size="small"
              @click="handleViewLogs(record.taskId, record.label)"
              class="inline-flex items-center"
            >
              <span class="i-mdi-text-box-outline mr-1" />
              {{ t("tuning.viewLogs") }}
            </a-button>
            <!-- Show progress bar when running -->
            <div v-if="record.status === 'running' && record.progress" class="flex-1 min-w-[120px]">
              <a-progress
                :percent="record.progress.percentage"
                :status="record.progress.percentage >= 100 ? 'success' : 'active'"
                :show-info="true"
                size="small"
              />
            </div>
            <!-- Show status tag when not running or no progress data -->
            <a-tag
              v-else
              :color="getStatusColor(record.status)"
              class="ml-2"
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

    <!-- ParamGrid Editor Dialog -->
    <ParamGridDialog
      v-model="paramGridDialogVisible"
      :model-name="currentEditModel"
      :model-label="currentEditModelLabel"
      :schema="currentModelSchema"
      :initial-values="paramGridValues[currentEditModel]"
      @save="handleSaveParamGrid"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from "vue";

const { t } = useI18n();

const props = defineProps<{
  availableModels: Array<{ label: string; value: string }>;
  tuningStatus: Record<string, string>;
  tuningTasks: Record<string, string>;
  tuningResults: any[];
  taskLogs: Record<string, any[]>;
  isTuning: boolean;
  taskProgress?: Record<string, { percentage: number; current: number; total: number; message?: string }>;
}>();

const emit = defineEmits<{
  "start-tune": [model: string, paramGrid?: Record<string, any>];
  "view-logs": [taskId: string, modelName: string];
}>();

const logModalVisible = ref(false);
const currentLogTaskId = ref<string>("");
const currentLogModelName = ref<string>("");

// ParamGrid dialog state
const paramGridDialogVisible = ref(false);
const currentEditModel = ref<string>("");
const currentEditModelLabel = ref<string>("");
const modelMetadata = ref<any[]>([]);
const paramGridValues = ref<Record<string, Record<string, any>>>({});

const columns = computed(() => [
  { title: t("tuning.model"), key: "model", dataIndex: "model" },
  { title: t("tuning.paramGridColumn"), key: "paramGrid", width: 150 },
  { title: t("tuning.tuning"), key: "action", width: 280 },
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

// Get schema for current model being edited
const currentModelSchema = computed(() => {
  const metadata = modelMetadata.value.find(
    (m) => m.name === currentEditModel.value
  );
  return metadata?.paramGridSchema || null;
});

// Combine all data sources into a single table data structure
const tableData = computed(() => {
  return props.availableModels.map((model) => {
    const status = props.tuningStatus[model.value];
    const taskId = props.tuningTasks[model.value];
    const result = props.tuningResults.find((r) => r.model === model.value);
    const progress = props.taskProgress?.[taskId];

    return {
      model: model.value,
      label: model.label,
      status: status,
      taskId: taskId,
      progress: progress,
      metrics: result
        ? {
            r2_test: result.r2_test,
            mse_test: result.mse_test,
            mae_test: result.mae_test,
          }
        : null,
    };
  });
});

const formatModelName = (name: string) => {
  return name.replace(/_/g, " ");
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

// Handle edit param grid
const handleEditParamGrid = (modelName: string, modelLabel: string) => {
  currentEditModel.value = modelName;
  currentEditModelLabel.value = modelLabel;
  paramGridDialogVisible.value = true;
};

// Handle save param grid
const handleSaveParamGrid = (values: Record<string, any>) => {
  paramGridValues.value[currentEditModel.value] = values;
};

const handleStartTune = (model: string) => {
  // Pass param grid if it exists for this model
  const paramGrid = paramGridValues.value[model];
  emit("start-tune", model, paramGrid);
};
</script>

<style scoped>
.model-tuning-table :deep(.ant-table-row:hover) {
  background-color: #f5f5f5;
}
</style>
