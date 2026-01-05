<template>
  <div class="space-y-6">
    <a-alert
      message="Model Tuning"
      description="Train machine learning models with hyperparameter tuning to find the best configuration."
      type="info"
      show-icon
      class="mb-4"
    />

    <div class="text-center py-12">
      <span class="i-mdi-settings text-6xl text-gray-400 mb-4"></span>
      <h3 class="text-xl font-semibold mb-2">Tuning Step</h3>
      <p class="text-gray-600 mb-4">
        Model tuning functionality will be implemented here.
      </p>
      <p class="text-sm text-gray-500">
        This includes model selection, hyperparameter configuration, and training execution.
      </p>
    </div>

    <div class="flex justify-between">
      <a-button @click="emit('back')">
        Back to Prepare
      </a-button>
      <a-button type="primary" @click="handleContinue">
        Continue to Predict (Demo)
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
const emit = defineEmits<{
  continue: [data: { model: string; parameters: Record<string, any>; taskId: number }];
  back: [];
}>();

const handleContinue = () => {
  // Demo: emit mock data to continue to prediction step
  emit('continue', {
    model: 'linear_regression',
    parameters: {},
    taskId: 1,
  });
};
</script>
