<template>
  <div class="space-y-6">
    <a-alert
      message="Make Predictions"
      description="Use your trained model to make predictions on new data."
      type="info"
      show-icon
      class="mb-4"
    />

    <div class="text-center py-12">
      <span class="i-mdi-chart-line text-6xl text-gray-400 mb-4"></span>
      <h3 class="text-xl font-semibold mb-2">Prediction Step</h3>
      <p class="text-gray-600 mb-4">
        Prediction functionality will be implemented here.
      </p>
      <div class="text-sm text-gray-500 space-y-1">
        <p><strong>Model:</strong> {{ selectedModel }}</p>
        <p v-if="taskId"><strong>Task ID:</strong> {{ taskId }}</p>
      </div>
    </div>

    <div class="flex justify-between">
      <a-button @click="emit('back')">
        Back to Tuning
      </a-button>
      <a-button type="primary" danger @click="emit('reset')">
        Reset Workflow
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  selectedModel: string | null;
  selectedParameters: Record<string, any>;
  taskId: number | null;
}>();

const emit = defineEmits<{
  back: [];
  reset: [];
}>();
</script>
