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
        <ModelTuningRow
          :column="column"
          :record="record"
          v-model:selectedTaskId="modelValue"
          :isTuning="isTuning"
          @auto-tune="handleAutoTune"
          @manual-train="handleManualTrain"
          @view-logs="handleViewLogs"
        />
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
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useModelTuningTableData } from "../composables/useModelTuningTableData";
import { useDialogManagement } from "../composables/useDialogManagement";
import { useFormatters } from "../composables/useFormatters";
import ModelTuningRow from "./ModelTuningRow.vue";

const { t } = useI18n();

const props = defineProps<{
  workItemId: number;
}>();

const modelValue = defineModel<number | null>("selectedTaskId", {
  default: null,
});

const emit = defineEmits<{
  "start-tune": [
    model: string,
    paramGrid?: Record<string, any>,
    trainingType?: string,
    parentTaskId?: number
  ];
  "view-logs": [taskId: number, modelName: string];
}>();

// Use composables
const {
  availableModels,
  tuningStatus,
  tuningTasks,
  tuningResults,
  taskLogs,
  isTuning,
  expandedKeys,
  tableData,
  getRowKey,
  handleExpand,
  fetchTaskLogs,
} = useModelTuningTableData(props.workItemId);

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
  return taskLogs.value[currentLogTaskId.value] || [];
});

// Event handlers
const handleViewLogs = (taskId: number, modelName: string) => {
  openLogModal(taskId, modelName);
  fetchTaskLogs(taskId);
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
  const parentTaskId = (tuningTasks.value[currentEditModel.value] || null) as
    | number
    | null;
  // Start manual train with single values
  emit(
    "start-tune",
    currentEditModel.value,
    values,
    "manual",
    parentTaskId || undefined
  );
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
