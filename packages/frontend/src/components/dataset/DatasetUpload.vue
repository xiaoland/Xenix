<template>
  <div class="space-y-4">
    <a-form layout="vertical">
      <a-form-item label="Dataset Name" required>
        <a-input v-model:value="datasetName" placeholder="Enter dataset name" />
      </a-form-item>

      <a-form-item label="Select File" required>
        <a-upload
          v-model:file-list="fileList"
          :before-upload="beforeUpload"
          accept=".csv,.xlsx,.xls"
          :max-count="1"
        >
          <a-button class="inline-flex items-center">
            <span class="i-mdi-file-upload mr-2"></span>
            Select File
          </a-button>
        </a-upload>
        <p class="text-sm text-gray-500 mt-2">
          Supported formats: CSV, Excel (.xlsx, .xls)
        </p>
      </a-form-item>
    </a-form>

    <div class="flex justify-end space-x-2">
      <a-button @click="emit('cancel')"> Cancel </a-button>
      <a-button
        type="primary"
        :loading="uploading"
        :disabled="!canUpload"
        @click="handleUpload"
      >
        Upload
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue';
import type { UploadProps } from 'ant-design-vue';

import { computed, ref } from 'vue';

import { useUploadDataset } from '../../composables';

const props = defineProps<{
  projectId: number;
}>();

const emit = defineEmits<{
  success: [];
  cancel: [];
}>();

const datasetName = ref('');
const fileList = ref<any[]>([]);

// Use composable for upload
const { mutate: uploadDataset, isPending: uploading } = useUploadDataset();

const canUpload = computed(() => {
  return datasetName.value.trim() !== '' && fileList.value.length > 0;
});

const beforeUpload: UploadProps['beforeUpload'] = (file) => {
  const isValidFormat =
    file.type === 'text/csv' ||
    file.type === 'application/vnd.ms-excel' ||
    file.type ===
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

  if (!isValidFormat) {
    message.error('You can only upload CSV or Excel files!');
    return false;
  }

  const isLt10M = file.size / 1024 / 1024 < 10;
  if (!isLt10M) {
    message.error('File must be smaller than 10MB!');
    return false;
  }

  return false; // Prevent auto upload
};

const handleUpload = () => {
  if (!canUpload.value) return;

  const formData = new FormData();
  formData.append('file', fileList.value[0].originFileObj);
  formData.append('name', datasetName.value);
  formData.append('projectId', String(props.projectId));

  uploadDataset(formData, {
    onSuccess: () => {
      message.success('Dataset uploaded successfully');
      emit('success');

      // Reset form
      datasetName.value = '';
      fileList.value = [];
    },
    onError: (error: any) => {
      console.error('Upload failed:', error);
      message.error('Failed to upload dataset');
    },
  });
};
</script>
