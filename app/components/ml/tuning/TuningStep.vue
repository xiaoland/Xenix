<template>
  <div class="space-y-6">
    <h2 class="text-2xl font-semibold mb-4">{{ $t("tuning.title") }}</h2>

    <!-- Integrated Model Tuning Table -->
    <ModelTuningTable
      :work-item-id="workItemId"
      v-model:selected-task-id="selectedTaskId"
    />

    <!-- Best Model Selection -->
    <div v-if="tuningResults.length > 0" class="mt-6">
      <h3 class="text-lg font-medium mb-3">
        {{ $t("tuning.selectBestForPrediction") }}
      </h3>
      <a-select
        :value="selectedBestModel"
        :placeholder="$t('tuning.selectModelPlaceholder')"
        class="w-full max-w-md"
        :dropdownMatchSelectWidth="false"
        @change="(val: any) => { selectedBestModel = val || null }"
      >
        <a-select-option
          v-for="result in tuningResults"
          :key="result.model"
          :value="result.model"
        >
          {{ formatModelName(result.model) }} (R²:
          {{ formatMetric(result.r2_test) }})
        </a-select-option>
      </a-select>
    </div>

    <!-- Navigation -->
    <div class="flex gap-4 mt-6">
      <a-button @click="emit('back')">
        {{ $t("tuning.back") }}
      </a-button>
      <a-button
        type="primary"
        :disabled="!selectedBestModel"
        @click="emit('continue', selectedBestModel!)"
      >
        {{ $t("tuning.continue") }}
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { message } from "ant-design-vue";
import { useModelTraining } from "../../../composables/useModelTraining";
import { useTaskPolling } from "../../../composables/useTaskPolling";
import { useDatasetRegistration } from "../../../composables/useDatasetRegistration";
import { WorkItemService } from "~/services";
import { useFormatters } from "../../../composables/useFormatters";
import ModelTuningTable from "./ModelTuningTable.vue";
import type { TuningResult } from "~/types";

const { t } = useI18n();
const { executeTrain } = useModelTraining();
const { pollTaskLogs, pollTaskStatus, registerTask, clearTasks } =
  useTaskPolling();
const { registerFileAsDataset } = useDatasetRegistration();

const props = defineProps<{
  workItemId: number;
  selectedTaskId?: number | null;
}>();

const emit = defineEmits<{
  "update:selectedTaskId": [taskId: number | null];
  continue: [model: string];
  back: [];
}>();

// Use formatters composable
const { formatModelName, formatMetric } = useFormatters();

// Local state
const selectedModels = ref<string[]>([]);
const activeLogTab = ref<string>("");
const selectedBestModel = ref<string | null>(null);
const selectedTaskId = ref<number | null>(props.selectedTaskId || null);
const tuningResults = ref<TuningResult[]>([]);

const localSelectedTaskId = computed({
  get: () => selectedTaskId.value,
  set: (value) => {
    selectedTaskId.value = value;
    emit("update:selectedTaskId", value);
  },
});

/**
 * Fetch existing tuning results for work item
 */
const fetchTuningResults = async (workItemId?: number) => {
  if (!workItemId) return;

  try {
    const response = await WorkItemService.fetchById(workItemId);
    if (response.success && response.workItem.tasks) {
      const tasks = response.workItem.tasks.filter(
        (t: any) => t.type === "auto-tune" && t.status === "completed"
      );

      // Build tuning results from completed tasks
      tuningResults.value = tasks.map((task: any) => ({
        model: task.parameter?.model || "",
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
        trainingType: task.parameter?.trainingType || "auto",
        createdAt: task.createdAt,
        taskId: task.id,
      }));

      // Register tasks for polling
      tasks.forEach((task: any) => {
        if (task.parameter?.model) {
          registerTask(task.parameter.model, task.id, task.status);
        }
      });
    }
  } catch (error) {
    console.error("Failed to fetch tuning results:", error);
  }
};

/**
 * Get or register dataset ID
 */
const getDatasetId = async (
  uploadedDatasetIdValue: string,
  trainingFileList: any[]
): Promise<string | null> => {
  let datasetIdToUse = uploadedDatasetIdValue;

  if (!datasetIdToUse && trainingFileList.length > 0) {
    const file = trainingFileList[0].originFileObj;
    const registeredId = await registerFileAsDataset(file);
    if (registeredId) {
      datasetIdToUse = registeredId;
    }
  }

  if (!datasetIdToUse) {
    message.error(t("messages.datasetRegistrationFailed"));
    return null;
  }

  return datasetIdToUse;
};

/**
 * Start tuning all selected models
 */
const startBatchTuning = async (params: {
  uploadedDatasetId: string;
  trainingFileList: any[];
  selectedFeatureColumns: string[];
  selectedTargetColumn: string;
  workItemId?: number;
}) => {
  if (!params.uploadedDatasetId && params.trainingFileList.length === 0) {
    message.error(t("messages.uploadError"));
    return;
  }

  const datasetIdToUse = await getDatasetId(
    params.uploadedDatasetId,
    params.trainingFileList
  );
  if (!datasetIdToUse) return;

  // Train all selected models
  for (const modelValue of selectedModels.value) {
    const response = await executeTrain(
      {
        datasetId: datasetIdToUse,
        featureColumns: params.selectedFeatureColumns,
        targetColumn: params.selectedTargetColumn,
        model: modelValue,
        workItemId: params.workItemId,
      },
      "auto"
    );

    if (response) {
      registerTask(modelValue, response.taskId);
      activeLogTab.value = response.taskId.toString();
      pollTaskStatus(response.taskId, modelValue).then(() =>
        fetchTuningResults(params.workItemId)
      );
      pollTaskLogs(response.taskId);
    }
  }
};

/**
 * Start tuning a single model
 */
const startSingleModelTuning = async (
  params: {
    uploadedDatasetId: string;
    trainingFileList: any[];
    selectedFeatureColumns: string[];
    selectedTargetColumn: string;
    workItemId?: number;
  },
  modelValue: string,
  paramGrid?: Record<string, any>,
  trainingType?: string,
  parentTaskId?: number
) => {
  const datasetIdToUse = await getDatasetId(
    params.uploadedDatasetId,
    params.trainingFileList
  );
  if (!datasetIdToUse) return;

  const response = await executeTrain(
    {
      datasetId: datasetIdToUse,
      featureColumns: params.selectedFeatureColumns,
      targetColumn: params.selectedTargetColumn,
      model: modelValue,
      paramGrid: paramGrid,
      workItemId: params.workItemId,
    },
    trainingType === "manual" ? "manual" : "auto"
  );

  if (response) {
    registerTask(modelValue, response.taskId, "pending");
    activeLogTab.value = response.taskId.toString();
    pollTaskStatus(response.taskId, modelValue).then(() =>
      fetchTuningResults(params.workItemId)
    );
    pollTaskLogs(response.taskId);
  }
};

/**
 * Reset tuning step state
 */
const resetTuningStep = () => {
  selectedModels.value = [];
  selectedBestModel.value = null;
  selectedTaskId.value = null;
  activeLogTab.value = "";
  tuningResults.value = [];
  clearTasks();
};

onMounted(() => {
  fetchTuningResults(props.workItemId);
});
</script>
