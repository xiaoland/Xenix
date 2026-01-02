<template>
  <div class="space-y-6">
    <h2 class="text-2xl font-semibold mb-4">{{ $t("tuning.title") }}</h2>

    <!-- Integrated Model Tuning Table -->
    <ModelTuningTable
      :work-item-id="workItemId"
      v-model:selected-task-id="selectedTaskId"
    />

    <!-- Navigation -->
    <div class="flex gap-4 mt-6">
      <a-button @click="emit('back')">
        {{ $t("tuning.back") }}
      </a-button>
      <a-button
        type="primary"
        :disabled="!selectedTaskId"
        @click="handleContinue"
      >
        {{ $t("tuning.continue") }}
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import { message } from "ant-design-vue";
import { useModelTraining } from "../../../composables/useModelTraining";
import { useDatasetRegistration } from "../../../composables/useDatasetRegistration";
import { WorkItemService, TaskService } from "~/services";
import { useFormatters } from "../../../composables/useFormatters";
import ModelTuningTable from "./ModelTuningTable.vue";
import type { TuningResult } from "~/types";

const { t } = useI18n();
const { executeTrain } = useModelTraining();
const { registerFileAsDataset } = useDatasetRegistration();

const props = defineProps<{
  workItemId: number;
  selectedTaskId?: number | null;
}>();

const emit = defineEmits<{
  "update:selectedTaskId": [taskId: number | null];
  continue: [
    data: { model: string; parameters: Record<string, any>; taskId: number }
  ];
  back: [];
}>();

/**
 * Handle continue button click - fetches task data and emits model + parameters
 */
const handleContinue = async () => {
  if (!selectedTaskId.value) return;

  try {
    const response = await TaskService.fetchStatus(selectedTaskId.value);
    if (response.task) {
      emit("continue", {
        model: response.task.parameter?.model || "",
        parameters: response.task.result?.params || {},
        taskId: selectedTaskId.value,
      });
    }
  } catch (error) {
    console.error("Failed to fetch task for continue:", error);
    message.error(t("messages.fetchTaskError"));
  }
};

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
    const response = await TaskService.fetchByWorkItemId(workItemId, [
      "auto-tune",
    ]);
    if (response.success && response.tasks) {
      const tasks = response.tasks.filter((t: any) => t.status === "completed");

      // Build tuning results from completed tasks
      tuningResults.value = tasks.map((task: any) => ({
        model: task.parameter?.model || "",
        params: task.result?.params || {},
        metrics: task.result?.metrics || {},
        r2: task.result?.metrics?.r2,
        status: task.status,
        trainingType: task.parameter?.trainingType || "auto",
        createdAt: task.createdAt,
        taskId: task.id,
      }));
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
      activeLogTab.value = response.taskId.toString();
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
    activeLogTab.value = response.taskId.toString();
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
};

// Watch for task selection changes and sync with selectedBestModel
watch(selectedTaskId, async (taskId) => {
  if (taskId) {
    try {
      const response = await TaskService.fetchStatus(taskId);
      if (response.task) {
        const model = response.task.parameter?.model;
        if (model) {
          selectedBestModel.value = model;
        }
      }
    } catch (error) {
      console.error("Failed to fetch selected task:", error);
    }
  }
});

onMounted(() => {
  fetchTuningResults(props.workItemId);
});
</script>
