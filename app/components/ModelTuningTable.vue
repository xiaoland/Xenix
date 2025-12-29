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
      :expandable="{
        expandedRowKeys: expandedKeys,
        onExpand: handleExpand,
      }"
      class="model-tuning-table"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'select'">
          <!-- Only show radio button in sub-rows (history items) -->
          <a-radio
            v-if="record.isHistory"
            :checked="selectedTaskId === record.taskId"
            @click="handleSelectTask(record.taskId, record.model)"
          />
        </template>
        <template v-else-if="column.key === 'model'">
          <span class="font-medium" :class="{ 'pl-2': record.isHistory }">
            {{
              record.isHistory
                ? `${formatTimestamp(record.createdAt)}`
                : formatModelName(record.label)
            }}
          </span>
        </template>
        <template v-else-if="column.key === 'tuneType'">
          <!-- Show tune type and parameters for sub-rows -->
          <div v-if="record.isHistory" class="text-sm">
            <div class="font-medium mb-1">
              <a-tag v-if="record.trainingType === 'auto-tune'" color="blue">
                {{ t("tuning.autoTune") }}
              </a-tag>
              <a-tag v-else-if="record.trainingType === 'train'" color="green">
                {{ t("tuning.manualTrain") }}
              </a-tag>
            </div>
            <div v-if="record.params" class="text-xs text-gray-600">
              <div
                v-for="(value, key) in record.params"
                :key="key"
                class="truncate"
              >
                <span class="font-medium">{{ key }}:</span>
                {{ formatParamValue(value) }}
              </div>
            </div>
          </div>
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
            <a-tag v-if="record.status" :color="getStatusColor(record.status)">
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
import { computed, toRef } from "vue";
import { useI18n } from "vue-i18n";
import { useTrainingHistory } from "../composables/useTrainingHistory";
import { useTableData } from "../composables/useTableData";
import { useDialogManagement } from "../composables/useDialogManagement";
import { useFormatters } from "../composables/useFormatters";

const { t } = useI18n();

const props = defineProps<{
  availableModels: Array<{ label: string; value: string }>;
  tuningStatus: Record<string, string>;
  tuningTasks: Record<string, number>;
  tuningResults: any[];
  taskLogs: Record<string, any[]>;
  isTuning: boolean;
  selectedTaskId?: number | null;
}>();

const emit = defineEmits<{
  "start-tune": [
    model: string,
    paramGrid?: Record<string, any>,
    trainingType?: string,
    parentTaskId?: number
  ];
  "view-logs": [taskId: number, modelName: string];
  "select-task": [taskId: number, model: string];
}>();

// Use composables
const { trainingHistory, expandedKeys, handleExpand } = useTrainingHistory(
  toRef(props, "tuningResults")
);

const { tableData, getRowKey } = useTableData(
  toRef(props, "availableModels"),
  toRef(props, "tuningStatus"),
  toRef(props, "tuningTasks"),
  toRef(props, "tuningResults"),
  trainingHistory
);

const {
  logModalVisible,
  paramGridDialogVisible,
  manualTrainDialogVisible,
  currentLogTaskId,
  currentLogModelName,
  currentEditModel,
  currentEditModelLabel,
  currentModelSchema,
  paramGridValues,
  manualTrainValues,
  openAutoTuneDialog,
  openManualTrainDialog,
  openLogModal,
} = useDialogManagement();

const { formatModelName, formatTimestamp, formatMetric, getStatusColor } =
  useFormatters();

// Format parameter values for display
const formatParamValue = (value: any): string => {
  if (Array.isArray(value)) {
    return `[${value.join(", ")}]`;
  }
  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value);
  }
  return String(value);
};

// Handle task selection
const handleSelectTask = (taskId: number, model: string) => {
  emit("select-task", taskId, model);
};

// Table columns
const columns = computed(() => [
  { title: "", key: "select", width: 50 },
  { title: t("tuning.model"), key: "model", dataIndex: "model" },
  { title: t("tuning.tuneType"), key: "tuneType", width: 200 },
  { title: t("tuning.tuning"), key: "action", width: 350 },
  { title: t("tuning.metrics"), key: "metrics", width: 320 },
]);

// Current logs computed property
const currentLogs = computed(() => {
  if (!currentLogTaskId.value) return [];
  return props.taskLogs[currentLogTaskId.value] || [];
});

// Event handlers
const handleViewLogs = (taskId: number, modelName: string) => {
  openLogModal(taskId, modelName);
  emit("view-logs", taskId, modelName);
};

const handleAutoTune = (modelName: string, modelLabel: string) => {
  openAutoTuneDialog(modelName, modelLabel);
};

const handleManualTrain = (modelName: string, modelLabel: string) => {
  openManualTrainDialog(modelName, modelLabel);
};

const handleSaveAutoTune = (values: Record<string, any>) => {
  paramGridValues.value[currentEditModel.value] = values;
  // Start auto-tune with param grid
  emit("start-tune", currentEditModel.value, values, "auto");
};

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
