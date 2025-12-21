<template>
  <div class="space-y-6">
    <h2 class="text-2xl font-semibold mb-4">Model Training</h2>

    <!-- Model Selector -->
    <ModelSelector
      v-model="localSelectedModels"
      :available-models="availableModels"
      :tuning-status="tuningStatus"
    />

    <!-- Tuning Action -->
    <div class="flex gap-4">
      <a-button
        type="primary"
        size="large"
        :loading="isTuning"
        :disabled="localSelectedModels.length === 0 || isTuning"
        @click="emit('start-tuning')"
      >
        <i class="i-mdi-tune mr-2"></i>
        Start Hyperparameter Tuning
      </a-button>
    </div>

    <!-- Task Logs Viewer -->
    <TaskLogViewer
      v-if="Object.keys(tuningTasks).length > 0"
      v-model="localActiveLogTab"
      :tuning-tasks="tuningTasks"
      :task-logs="taskLogs"
    />

    <!-- Tuning Results -->
    <TuningResults
      :results="tuningResults"
      :selected-model="localSelectedBestModel"
      @update:selected-model="emit('update:selected-best-model', $event)"
    />

    <!-- Navigation -->
    <div class="flex gap-4 mt-6">
      <a-button @click="emit('back')">Back to Upload</a-button>
      <a-button
        type="primary"
        :disabled="!localSelectedBestModel"
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
  tuningResults: any[];
  taskLogs: Record<string, any[]>;
  activeLogTab: string;
  selectedBestModel: string | null;
}>();

const emit = defineEmits<{
  'start-tuning': [];
  'back': [];
  'continue': [];
  'update:selectedModels': [models: string[]];
  'update:activeLogTab': [tab: string];
  'update:selected-best-model': [model: string];
}>();

const localSelectedModels = computed({
  get: () => props.selectedModels,
  set: (value) => emit('update:selectedModels', value)
});

const localActiveLogTab = computed({
  get: () => props.activeLogTab,
  set: (value) => emit('update:activeLogTab', value)
});

const localSelectedBestModel = computed({
  get: () => props.selectedBestModel,
  set: (value) => emit('update:selected-best-model', value || '')
});
</script>
