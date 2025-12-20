<template>
  <div class="space-y-4">
    <h2 class="text-2xl font-semibold mb-4">Make Predictions</h2>

    <a-alert
      v-if="bestModel"
      :message="`Best Model: ${bestModel}`"
      type="success"
      show-icon
      class="mb-4"
    />

    <a-upload-dragger
      v-model:file-list="fileList"
      name="file"
      :before-upload="beforeUpload"
      :max-count="1"
      accept=".xlsx,.xls"
    >
      <p class="ant-upload-drag-icon">
        <i class="i-mdi-file-table text-6xl text-green-500"></i>
      </p>
      <p class="ant-upload-text">Upload data for prediction</p>
      <p class="ant-upload-hint">
        The file should have the same features as the training data.
      </p>
    </a-upload-dragger>

    <a-button
      type="primary"
      size="large"
      block
      :loading="isPredicting"
      :disabled="fileList.length === 0"
      @click="$emit('predict')"
    >
      <i class="i-mdi-chart-line mr-2"></i>
      Generate Predictions
    </a-button>

    <div v-if="predictionTask" class="mt-4">
      <a-alert
        :message="predictionMessage"
        :type="predictionType"
        show-icon
      />
    </div>

    <div class="flex gap-4 mt-6">
      <a-button @click="$emit('back')">Back</a-button>
      <a-button @click="$emit('reset')">Start Over</a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { UploadProps } from 'ant-design-vue';
import { message } from 'ant-design-vue';

const props = defineProps<{
  bestModel: string | null;
  isPredicting: boolean;
  predictionTask: any;
}>();

const fileList = defineModel<any[]>({ required: true });

defineEmits<{
  predict: [];
  back: [];
  reset: [];
}>();

const predictionMessage = computed(() => {
  if (!props.predictionTask) return '';
  
  switch (props.predictionTask.status) {
    case 'pending':
      return 'Prediction task queued...';
    case 'running':
      return 'Generating predictions...';
    case 'completed':
      return 'Predictions completed successfully!';
    case 'failed':
      return `Prediction failed: ${props.predictionTask.error || 'Unknown error'}`;
    default:
      return '';
  }
});

const predictionType = computed(() => {
  if (!props.predictionTask) return 'info';
  
  switch (props.predictionTask.status) {
    case 'completed':
      return 'success';
    case 'failed':
      return 'error';
    default:
      return 'info';
  }
});

const beforeUpload: UploadProps['beforeUpload'] = (file) => {
  const isExcel = file.name.endsWith('.xlsx') || file.name.endsWith('.xls');
  if (!isExcel) {
    message.error('You can only upload Excel files!');
  }
  return false; // Prevent auto upload
};
</script>

<style scoped>
.ant-upload-drag-icon {
  margin-bottom: 1rem;
}
</style>
