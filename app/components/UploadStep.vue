<template>
  <div class="space-y-4">
    <h2 class="text-2xl font-semibold mb-4">Upload Training Data</h2>
    
    <a-upload-dragger
      v-model:file-list="fileList"
      name="file"
      :before-upload="beforeUpload"
      :max-count="1"
      accept=".xlsx,.xls"
    >
      <p class="ant-upload-drag-icon">
        <i class="i-mdi-cloud-upload text-6xl text-blue-500"></i>
      </p>
      <p class="ant-upload-text">Click or drag file to upload training data</p>
      <p class="ant-upload-hint">
        Support for Excel files (.xlsx, .xls). Data should contain features and target variable.
      </p>
    </a-upload-dragger>

    <a-button 
      type="primary" 
      size="large" 
      block
      :disabled="fileList.length === 0"
      @click="$emit('continue')"
    >
      Continue to Model Training
    </a-button>
  </div>
</template>

<script setup lang="ts">
import type { UploadProps } from 'ant-design-vue';
import { message } from 'ant-design-vue';

const fileList = defineModel<any[]>({ required: true });

defineEmits<{
  continue: []
}>();

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
