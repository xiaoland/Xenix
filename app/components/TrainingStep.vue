<template>
  <div class="space-y-6">
    <h2 class="text-2xl font-semibold mb-4">Model Training & Comparison</h2>

    <!-- Model Selector -->
    <ModelSelector
      v-model="localSelectedModels"
      :available-models="availableModels"
      :tuning-status="tuningStatus"
      @toggle="emit('model-toggle', $event)"
    />

    <!-- Tuning Actions -->
    <div class="flex gap-4">
      <a-button
        type="primary"
        size="large"
        :loading="isTuning"
        :disabled="localSelectedModels.length === 0"
        @click="emit('start-tuning')"
      >
        <i class="i-mdi-tune mr-2"></i>
        Start Hyperparameter Tuning
      </a-button>

      <a-button
        type="default"
        size="large"
        :loading="isComparing"
        :disabled="!canCompare"
        @click="emit('start-comparison')"
      >
        <i class="i-mdi-compare mr-2"></i>
        Compare All Models
      </a-button>
    </div>

    <!-- Task Logs Viewer -->
    <TaskLogViewer
      v-model="localActiveLogTab"
      :tuning-tasks="tuningTasks"
      :comparison-task-id="comparisonTaskId"
      :task-logs="taskLogs"
    />

    <!-- Comparison Results -->
    <ComparisonResults :comparison-results="comparisonResults" />

    <!-- Navigation -->
    <div class="flex gap-4 mt-6">
      <a-button @click="emit('back')">Back</a-button>
      <a-button
        type="primary"
        :disabled="!comparisonResults"
        @click="emit('continue')"
      >
        Continue to Prediction
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  availableModels: Array<{ label: string; value: string }>;
  selectedModels: string[];
  tuningStatus: Record<string, string>;
  tuningTasks: Record<string, string>;
  isTuning: boolean;
  isComparing: boolean;
  comparisonResults: any;
  comparisonTaskId: string | null;
  taskLogs: Record<string, any[]>;
  activeLogTab: string;
}>();

const emit = defineEmits<{
  'model-toggle': [modelValue: string];
  'start-tuning': [];
  'start-comparison': [];
  'back': [];
  'continue': [];
  'update:selectedModels': [models: string[]];
  'update:activeLogTab': [tab: string];
}>();

const localSelectedModels = computed({
  get: () => props.selectedModels,
  set: (value) => emit('update:selectedModels', value)
});

const localActiveLogTab = computed({
  get: () => props.activeLogTab,
  set: (value) => emit('update:activeLogTab', value)
});

const canCompare = computed(() => {
  return Object.values(props.tuningStatus).some(status => status === 'completed');
});
</script>
