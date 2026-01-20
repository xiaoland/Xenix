<template>
  <div class="space-y-6">
    <h2 class="text-2xl font-semibold mb-4">
      {{ $t("ml.tuning.title") }}
    </h2>

    <a-alert
      :message="$t('ml.tuning.trainDescription')"
      type="info"
      show-icon
      class="mb-4"
    />

    <!-- Model Selection and Actions -->
    <div class="bg-white rounded-lg border p-4 mb-4">
      <h3 class="text-lg font-medium mb-3">
        {{ $t("ml.tuning.selectModels") }}
      </h3>
      <a-select
        v-model:value="selectedModels"
        mode="multiple"
        :placeholder="$t('ml.tuning.selectPlaceholder')"
        style="width: 100%"
        :options="availableModels"
        :loading="isLoadingModels"
        class="mb-3"
      />

      <div class="flex gap-2">
        <a-button
          type="primary"
          class="inline-flex items-center"
          :loading="isTraining"
          :disabled="selectedModels.length === 0"
          @click="handleStartAutoTune"
        >
          <span class="i-mdi-auto-fix mr-1"></span>
          {{ $t("ml.tuning.startAutoTune") }}
        </a-button>
        <a-button
          class="inline-flex items-center"
          @click="showManualTuneDialog = true"
        >
          <span class="i-mdi-tune mr-1"></span>
          {{ $t("ml.tuning.manualTune") }}
        </a-button>
        <a-button
          danger
          class="inline-flex items-center"
          @click="handleClearFailedTasks"
        >
          <span class="i-mdi-delete-outline mr-1"></span>
          {{ $t("ml.tuning.clearFailedTasks") }}
        </a-button>
      </div>
    </div>

    <!-- Tasks Table -->
    <ModelTuningTable
      ref="tuningTableRef"
      :work-item-id="workItemId"
      :selected-task-id="selectedTaskId"
      @select-task="handleSelectTask"
    />

    <!-- Navigation -->
    <div class="flex justify-between">
      <a-button @click="emit('back')">
        {{ $t("ml.tuning.backToPrepare") }}
      </a-button>
      <a-button
        type="primary"
        :disabled="!selectedTaskId"
        @click="handleContinue"
      >
        {{ $t("ml.tuning.continueToPredict") }}
      </a-button>
    </div>

    <!-- Manual Tune Dialog -->
    <ManualTuneDialog v-model="showManualTuneDialog" @tune="handleManualTune" />
  </div>
</template>

<script setup lang="ts">
import { message } from "ant-design-vue";

import { ref } from "vue";

import { client } from "../../../api/client";
import { useGroupedModels } from "@/composables";
import ManualTuneDialog from "./ManualTuneDialog.vue";
import ModelTuningTable from "./ModelTuningTable.vue";

const props = defineProps<{
  workItemId: number;
  datasetId: number | null;
  featureColumns: string[];
  targetColumn: string;
}>();

const emit = defineEmits<{
  continue: [
    data: { model: string; parameters: Record<string, any>; taskId: number },
  ];
  back: [];
}>();

// State
const selectedModels = ref<string[]>([]);
const selectedTaskId = ref<number | null>(null);
const isTraining = ref(false);
const showManualTuneDialog = ref(false);
const tuningTableRef = ref<InstanceType<typeof ModelTuningTable>>();

// Fetch available models from backend (grouped by category)
const { data: availableModels, isLoading: isLoadingModels } =
  useGroupedModels();

/**
 * Start auto-tune for selected models
 */
const handleStartAutoTune = async () => {
  isTraining.value = true;
  try {
    // Start training for each selected model
    for (const model of selectedModels.value) {
      const response = await client.train["batch"].$post({
        json: {
          datasetId: props.datasetId ?? undefined,
          featureColumns: props.featureColumns,
          targetColumn: props.targetColumn,
          model,
          workItemId: props.workItemId,
        },
      });
      if (!response.ok) throw new Error("Failed to start auto tune");
    }
    message.success(
      `Started training for ${selectedModels.value.length} model(s)`,
    );
    selectedModels.value = [];
    // Refresh tasks table
    tuningTableRef.value?.refetch();
  } catch (error: any) {
    console.error("Failed to start training:", error);
    message.error(error.message || "Failed to start training");
  } finally {
    isTraining.value = false;
  }
};

/**
 * Handle manual tune submission
 */
const handleManualTune = async (data: {
  model: string;
  parameters: Record<string, any>;
}) => {
  try {
    const response = await client.train["single"].$post({
      json: {
        datasetId: props.datasetId ?? undefined,
        featureColumns: props.featureColumns,
        targetColumn: props.targetColumn,
        model: data.model,
        parameters: data.parameters,
        workItemId: props.workItemId,
      },
    });
    if (!response.ok) throw new Error("Failed to start manual tune");

    message.success("Manual training started");
    // Refresh tasks table
    tuningTableRef.value?.refetch();
  } catch (error: any) {
    console.error("Failed to start manual tune:", error);
    message.error(error.message || "Failed to start manual training");
  }
};

/**
 * Clear all failed tasks
 */
const handleClearFailedTasks = async () => {
  try {
    message.info("Task deletion feature coming soon");
  } catch (error: any) {
    console.error("Failed to clear tasks:", error);
    message.error(error.message || "Failed to clear tasks");
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
    const response = await client.tasks[":id"].$get({
      param: { id: String(selectedTaskId.value) },
    });
    if (!response.ok) throw new Error("Failed to fetch task");
    const data = await response.json();
    if (data) {
      emit("continue", {
        model: (data.parameter as any)?.model || "",
        parameters: (data.result as any)?.params || {},
        taskId: selectedTaskId.value,
      });
    }
  } catch (error: any) {
    console.error("Failed to fetch task:", error);
    message.error(error.message || "Failed to fetch task details");
  }
};
</script>

<style scoped>
.params-display .param-row,
.params-display .metric-row {
  display: flex;
  align-items: center;
}

.param-key,
.metric-key {
  min-width: 120px;
}
</style>
