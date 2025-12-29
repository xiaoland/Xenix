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
import { useDialogManagement } from "../composables/useDialogManagement";
import { useFormatters } from "../composables/useFormatters";
import ModelTuningRow from "./ModelTuningRow.vue";
import { ref, watch, toRef } from "vue";
import { WorkItemService, TaskService } from "~/services";
import type { TuningResult } from "~/types";

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

const workItemIdRef = toRef(() => props.workItemId);

// Data states
const availableModels = ref<Array<{ label: string; value: string }>>([]);
const tuningStatus = ref<Record<string, string>>({});
const tuningTasks = ref<Record<string, number>>({});
const tuningResults = ref<TuningResult[]>([]);
const taskLogs = ref<Record<string, any[]>>({});
const trainingHistory = ref<Record<string, any[]>>({});
const isTuning = ref(false);

// UI states
const expandedKeys = ref<string[]>([]);

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

// Table data computed property
const tableData = computed(() => {
  const data: any[] = [];

  for (const model of availableModels.value) {
    const status = tuningStatus.value[model.value];
    const taskId = tuningTasks.value[model.value];
    const result = tuningResults.value.find(
      (r: any) => r.model === model.value
    );

    // Build children array for expandable rows
    const children: any[] = [];

    // Add historical tasks
    const history = trainingHistory.value[model.value] || [];
    for (const historyItem of history) {
      children.push({
        model: model.value,
        label: model.label,
        taskId: historyItem.taskId,
        status: historyItem.status || "completed",
        metrics: {
          r2_test: historyItem.r2_test,
          mse_test: historyItem.mse_test,
          mae_test: historyItem.mae_test,
        },
        params: historyItem.params,
        trainingType: historyItem.trainingType,
        createdAt: historyItem.createdAt,
        isHistory: true,
      });
    }

    // Add current active task if not in history
    if (status && taskId) {
      const existsInHistory = history.some((h: any) => h.taskId === taskId);
      if (!existsInHistory) {
        children.push({
          model: model.value,
          label: model.label,
          taskId: taskId,
          status: status,
          metrics: result
            ? {
                r2_test: result.metrics?.r2_test,
                mse_test: result.metrics?.mse_test,
                mae_test: result.metrics?.mae_test,
              }
            : null,
          params: result?.params,
          trainingType: result?.trainingType || "auto",
          createdAt: result?.createdAt || new Date(),
          isHistory: true,
          isCurrent: true,
        });
      }
    }

    // Parent row
    const parentRow = {
      model: model.value,
      label: model.label,
      children: children,
      isHistory: false,
    };

    data.push(parentRow);
  }

  return data;
});

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

// Functions from composable
const fetchTuningData = async () => {
  if (!workItemIdRef.value) return;

  try {
    const response = await WorkItemService.fetchById(workItemIdRef.value);
    if (response.success && response.workItem) {
      const workItem = response.workItem;

      // Extract available models from tasks or use defaults
      const models = new Set<string>();
      if (workItem.tasks) {
        workItem.tasks.forEach((task: any) => {
          if (task.parameter?.model) {
            models.add(task.parameter.model);
          }
        });
      }

      // Build available models list (use i18n translation if available)
      const modelsList = Array.from(models).map((model) => {
        const translated = t(`models.${model.replace(".", "_")}`);
        const base = model.split(".").pop() || model;
        const label =
          translated === model ? base.replace(/_/g, " ") : translated;
        return { label, value: model };
      });
      availableModels.value = modelsList;

      // Process tasks and build status, tuningTasks, and results
      const statusMap: Record<string, string> = {};
      const tasksMap: Record<string, number> = {};
      const resultsMap: TuningResult[] = [];

      if (workItem.tasks) {
        for (const task of workItem.tasks as any[]) {
          const model = task.parameter?.model;
          if (!model) continue;

          statusMap[model] = task.status || "pending";
          if (task.id) {
            tasksMap[model] = task.id;
          }

          // Collect completed tuning results
          if (task.type === "auto-tune" && task.status === "completed") {
            resultsMap.push({
              model: model,
              params: task.result?.params || {},
              metrics: {
                mse_train: task.result?.mse_train,
                mae_train: task.result?.mae_train,
                r2_train: task.result?.r2_train,
                mse_test: task.result?.mse_test,
                mae_test: task.result?.mae_test,
                r2_test: task.result?.r2_test,
              },
              status: task.status,
              trainingType: task.parameter?.trainingType || "auto-tune",
              createdAt: task.createdAt,
              taskId: task.id,
            } as any);
          }
        }
      }

      tuningStatus.value = statusMap;
      tuningTasks.value = tasksMap;
      tuningResults.value = resultsMap;

      // Determine if tuning is in progress
      isTuning.value = Object.values(statusMap).some(
        (status) => status === "processing" || status === "pending"
      );

      // Fetch training history for each model
      for (const model of modelsList) {
        await fetchTrainingHistory(model.value);
      }
    }
  } catch (error) {
    console.error("Failed to fetch tuning data:", error);
  }
};

const fetchTrainingHistory = async (model: string) => {
  try {
    const response = await TaskService.fetchTrainingHistory(model);
    if (response.success && response.results) {
      trainingHistory.value[model] = response.results;
    }
  } catch (error) {
    console.error(`Failed to fetch training history for ${model}:`, error);
  }
};

const fetchTaskLogs = async (taskId: number) => {
  try {
    const response = await TaskService.fetchLogs(taskId);
    if (response.success && response.logs) {
      taskLogs.value[taskId] = response.logs;
    }
  } catch (error) {
    console.error(`Failed to fetch logs for task ${taskId}:`, error);
  }
};

const handleExpand = (expanded: boolean, record: any) => {
  if (expanded) {
    if (!expandedKeys.value.includes(record.model)) {
      expandedKeys.value.push(record.model);
    }
    fetchTrainingHistory(record.model);
  } else {
    expandedKeys.value = expandedKeys.value.filter(
      (key) => key !== record.model
    );
  }
};

const getRowKey = (record: any) => {
  return record.isHistory ? `${record.model}-${record.taskId}` : record.model;
};

// Watch for workItemId changes and refetch data
watch(
  workItemIdRef,
  () => {
    if (workItemIdRef.value) {
      fetchTuningData();
    }
  },
  { immediate: true }
);

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
