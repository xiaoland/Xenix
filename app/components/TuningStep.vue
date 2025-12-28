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
      :selected-task-id="localSelectedTaskId"
      @update:selected-models="localSelectedModels = $event"
      @update:selectedTaskId="localSelectedTaskId = $event"
      @start-tune="handleStartTune"
      @view-logs="handleViewLogs"
    />

    <!-- Best Model Selection -->
    <div v-if="tuningResults.length > 0" class="mt-6">
      <h3 class="text-lg font-medium mb-3">
        {{ $t("tuning.selectBestForPrediction") }}
      </h3>
      <p class="text-sm text-gray-600 mb-2">
        {{ $t("tuning.selectResultNote") }}
      </p>
      <a-alert
        v-if="!localSelectedTaskId"
        type="warning"
        :message="$t('tuning.noResultSelected')"
        show-icon
        class="mb-3"
      />
    </div>

    <!-- Navigation -->
    <div class="flex gap-4 mt-6">
      <a-button @click="emit('back')">{{ $t("tuning.back") }}</a-button>
      <a-button
        type="primary"
        :disabled="!localSelectedTaskId"
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
  tuningTasks: Record<string, number>;
  isTuning: boolean;
  tuningResults: any[];
  taskLogs: Record<string, any[]>;
  activeLogTab: string;
  selectedBestModel: string | null;
  selectedTaskId?: number | null; // Selected result task ID
}>();

const emit = defineEmits<{
  "start-tuning": [];
  "start-single-tune": [model: string, paramGrid?: Record<string, any>, trainingType?: string, parentTaskId?: number];
  back: [];
  continue: [];
  "update:selectedModels": [models: string[]];
  "update:activeLogTab": [tab: string];
  "update:selected-best-model": [model: string];
  "update:selectedTaskId": [taskId: number | null];
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

const localSelectedTaskId = computed({
  get: () => props.selectedTaskId,
  set: (value) => emit("update:selectedTaskId", value),
});

const handleStartTune = (model: string, paramGrid?: Record<string, any>, trainingType?: string, parentTaskId?: string) => {
  // Emit the single tune event for this specific model with optional param grid, training type, and parent task
  emit("start-single-tune", model, paramGrid, trainingType, parentTaskId);
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
