<template>
  <div class="space-y-6">
    <h2 class="text-2xl font-semibold mb-4">{{ $t("tuning.title") }}</h2>

    <!-- Integrated Model Tuning Table -->
    <ModelTuningTable
      :available-models="availableModels"
      :selected-models="localSelectedModels"
      :tuning-status="tuningStatus"
      :tuning-tasks="tuningTasks"
      :tuning-results="tuningResults"
      :task-logs="taskLogs"
      :is-tuning="isTuning"
      @update:selected-models="localSelectedModels = $event"
      @start-tune="handleStartTune"
      @view-logs="handleViewLogs"
    />

    <!-- Best Model Selection -->
    <div v-if="tuningResults.length > 0" class="mt-6">
      <h3 class="text-lg font-medium mb-3">
        {{ $t("tuning.selectBestForPrediction") }}
      </h3>
      <a-select
        v-model:value="localSelectedBestModel"
        :placeholder="$t('tuning.selectModelPlaceholder')"
        class="w-full max-w-md"
        :dropdownMatchSelectWidth="false"
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

const props = defineProps<{
  availableModels: Array<{ label: string; value: string }>;
  selectedModels: string[];
  tuningStatus: Record<string, string>;
  tuningTasks: Record<string, string>;
  isTuning: boolean;
  tuningResults: any[];
  taskLogs: Record<string, any[]>;
  activeLogTab: string;
  selectedBestModel: string | null;
}>();

const emit = defineEmits<{
  "start-tuning": [];
  "start-single-tune": [model: string];
  back: [];
  continue: [];
  "update:selectedModels": [models: string[]];
  "update:activeLogTab": [tab: string];
  "update:selected-best-model": [model: string];
}>();

const localSelectedModels = computed({
  get: () => props.selectedModels,
  set: (value) => emit("update:selectedModels", value),
});

const localActiveLogTab = computed({
  get: () => props.activeLogTab,
  set: (value) => emit("update:activeLogTab", value),
});

const localSelectedBestModel = computed({
  get: () => props.selectedBestModel,
  set: (value) => emit("update:selected-best-model", value || ""),
});

const handleStartTune = (model: string) => {
  // Emit the single tune event for this specific model
  emit("start-single-tune", model);
};

const handleViewLogs = (taskId: string, modelName: string) => {
  // Update the active log tab
  emit("update:activeLogTab", taskId);
};

const formatModelName = (name: string) => {
  return name.replace(/_/g, " ");
};

const formatMetric = (value: string | number) => {
  if (!value) return "N/A";
  const num = typeof value === "string" ? parseFloat(value) : value;
  return num.toFixed(4);
};
</script>
