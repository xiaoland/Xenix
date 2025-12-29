<template>
  <div class="space-y-6">
    <h2 class="text-2xl font-semibold mb-4">{{ $t("tuning.title") }}</h2>

    <!-- Integrated Model Tuning Table -->
    <ModelTuningTable
      :work-item-id="workItemId"
      v-model:selected-task-id="localSelectedTaskId"
      @start-tune="handleStartTune"
      @view-logs="handleViewLogs"
    />

    <!-- Best Model Selection -->
    <div v-if="tuningResults.length > 0" class="mt-6">
      <h3 class="text-lg font-medium mb-3">
        {{ $t("tuning.selectBestForPrediction") }}
      </h3>
      <a-select
        :value="localSelectedBestModel || undefined"
        :placeholder="$t('tuning.selectModelPlaceholder')"
        class="w-full max-w-md"
        :dropdownMatchSelectWidth="false"
        @change="(val: any) => { localSelectedBestModel = val || null }"
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
      <a-button @click="emit('back')">{{ $t("tuning.back") }}</a-button>
      <a-button
        type="primary"
        :disabled="!localSelectedBestModel"
        @click="emit('continue')"
      >
        {{ $t("tuning.continue") }}
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useFormatters } from "../composables/useFormatters";

const props = defineProps<{
  workItemId: number;
  selectedBestModel: string | null;
  selectedTaskId?: number | null;
  tuningResults: any[];
}>();

const emit = defineEmits<{
  back: [];
  continue: [];
  "update:selected-best-model": [model: string];
  "update:selected-task-id": [taskId: number | null];
  "start-tune": [
    model: string,
    paramGrid?: Record<string, any>,
    trainingType?: string,
    parentTaskId?: number
  ];
  "view-logs": [taskId: number, modelName: string];
}>();

// Use formatters composable
const { formatModelName, formatMetric } = useFormatters();

const localSelectedBestModel = computed({
  get: () => props.selectedBestModel,
  set: (value) => emit("update:selected-best-model", value || ""),
});

const localSelectedTaskId = computed({
  get: () => props.selectedTaskId || null,
  set: (value) => emit("update:selected-task-id", value),
});

const handleStartTune = (
  model: string,
  paramGrid?: Record<string, any>,
  trainingType?: string,
  parentTaskId?: number
) => {
  // Emit the tune event
  emit("start-tune", model, paramGrid, trainingType, parentTaskId);
};

const handleViewLogs = (taskId: number, modelName: string) => {
  // Handle view logs event
  console.log("View logs for task:", taskId, modelName);
};
</script>
