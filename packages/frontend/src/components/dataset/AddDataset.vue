<template>
  <div class="space-y-4">
    <a-form layout="vertical">
      <!-- Storage Type Selector -->
      <a-form-item label="Storage Type" required>
        <a-radio-group v-model:value="storageType" button-style="solid">
          <a-radio-button value="local">
            <span class="inline-flex items-center">
              <span class="i-mdi-harddisk mr-2"></span>
              Local (User's Device)
            </span>
          </a-radio-button>
          <a-radio-button value="oss">
            <span class="inline-flex items-center">
              <span class="i-mdi-cloud mr-2"></span>
              OSS (Cloud Storage)
            </span>
          </a-radio-button>
        </a-radio-group>
        <div class="text-sm text-gray-500 mt-1">
          <span v-if="storageType === 'local'">
            Dataset will reference a file on your local device. Upload step will be skipped.
          </span>
          <span v-else>
            Dataset will be uploaded to cloud storage.
          </span>
        </div>
      </a-form-item>

      <!-- Dataset Name -->
      <a-form-item label="Dataset Name" required>
        <a-input
          v-model:value="datasetName"
          placeholder="Enter dataset name"
        />
      </a-form-item>

      <!-- File Path (for local) or Upload (for OSS) -->
      <a-form-item v-if="storageType === 'local'" label="File Path" required>
        <a-input
          v-model:value="filePath"
          placeholder="e.g., /path/to/dataset.xlsx or C:\data\dataset.csv"
        />
        <div class="text-sm text-gray-500 mt-1">
          Enter the full path to the dataset file on your local system
        </div>
      </a-form-item>

      <a-form-item v-else label="Upload File" required>
        <a-upload-dragger
          v-model:file-list="fileList"
          :before-upload="beforeUpload"
          accept=".csv,.xlsx,.xls"
          :max-count="1"
          :show-upload-list="{ showRemoveIcon: true }"
          @change="handleFileChange"
        >
          <p class="ant-upload-drag-icon">
            <span class="i-mdi-cloud-upload text-4xl text-gray-400"></span>
          </p>
          <p class="ant-upload-text">
            Click or drag file to upload
          </p>
          <p class="ant-upload-hint">
            Supported formats: CSV, Excel (.xlsx, .xls)
          </p>
        </a-upload-dragger>
      </a-form-item>

      <!-- Metadata Display (auto-extracted) -->
      <div v-if="metadata" class="bg-gray-50 p-4 rounded-lg border">
        <h4 class="text-sm font-semibold mb-2">Dataset Information</h4>
        <div class="space-y-1 text-sm">
          <div><strong>Columns:</strong> {{ metadata.columns.length }}</div>
          <div><strong>Rows:</strong> {{ metadata.rowCount }}</div>
          <div><strong>Size:</strong> {{ formatFileSize(metadata.fileSize) }}</div>
          <div class="mt-2">
            <strong>Column Names:</strong>
            <div class="mt-1 flex flex-wrap gap-1">
              <a-tag v-for="col in metadata.columns" :key="col" size="small">
                {{ col }}
              </a-tag>
            </div>
          </div>
        </div>
      </div>
    </a-form>

    <div class="flex justify-end space-x-2">
      <a-button @click="emit('cancel')">
        Cancel
      </a-button>
      <a-button
        type="primary"
        :loading="creating"
        :disabled="!canCreate"
        @click="handleCreate"
      >
        {{ storageType === 'local' ? 'Create Dataset' : 'Upload & Create' }}
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { message } from "ant-design-vue";
import type { UploadProps } from "ant-design-vue";

import { computed, ref } from "vue";

import { useCreateDataset } from "../../composables";
import { extractDatasetMetadata, type DatasetMetadata } from "../../utils/datasetUtils";

const props = defineProps<{
  projectId: number;
}>();

const emit = defineEmits<{
  success: [];
  cancel: [];
}>();

const storageType = ref<'local' | 'oss'>('oss');
const datasetName = ref("");
const filePath = ref("");
const fileList = ref<any[]>([]);
const metadata = ref<DatasetMetadata | null>(null);

// Use composable for dataset creation
const { mutate: createDataset, isPending: creating } = useCreateDataset();

const canCreate = computed(() => {
  if (!datasetName.value.trim()) return false;
  if (!metadata.value) return false;

  if (storageType.value === 'local') {
    return filePath.value.trim() !== "";
  } else {
    return fileList.value.length > 0;
  }
});

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
};

const beforeUpload: UploadProps["beforeUpload"] = (file) => {
  const isValidFormat =
    file.type === "text/csv" ||
    file.type === "application/vnd.ms-excel" ||
    file.type ===
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

  if (!isValidFormat) {
    message.error("You can only upload CSV or Excel files!");
    return false;
  }

  const isLt10M = file.size / 1024 / 1024 < 10;
  if (!isLt10M) {
    message.error("File must be smaller than 10MB!");
    return false;
  }

  return false; // Prevent auto upload
};

const handleFileChange = async () => {
  if (fileList.value.length > 0) {
    try {
      const file = fileList.value[0].originFileObj;
      message.loading({ content: 'Analyzing file...', key: 'analyze' });
      metadata.value = await extractDatasetMetadata(file);
      message.success({ content: 'File analyzed successfully', key: 'analyze' });
    } catch (error: any) {
      message.error({ content: error.message || 'Failed to analyze file', key: 'analyze' });
      metadata.value = null;
    }
  } else {
    metadata.value = null;
  }
};

const handleCreate = async () => {
  if (!canCreate.value || !metadata.value) return;

  const params = {
    name: datasetName.value,
    projectId: props.projectId,
    storage: storageType.value,
    filePath: storageType.value === 'local' ? filePath.value : '',
    file: storageType.value === 'oss' ? fileList.value[0].originFileObj : null,
    columns: metadata.value.columns,
    rowCount: metadata.value.rowCount,
    fileSize: metadata.value.fileSize,
  };

  createDataset(params, {
    onSuccess: () => {
      message.success("Dataset created successfully");
      emit("success");

      // Reset form
      datasetName.value = "";
      filePath.value = "";
      fileList.value = [];
      metadata.value = null;
    },
    onError: (error: any) => {
      console.error("Creation failed:", error);
      message.error(error.message || "Failed to create dataset");
    },
  });
};

// For local storage, allow manual metadata input or file selection for analysis
const handleLocalFileSelect = async () => {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.csv,.xlsx,.xls';

  input.onchange = async (e: any) => {
    const file = e.target.files[0];
    if (file) {
      try {
        message.loading({ content: 'Analyzing file...', key: 'analyze' });
        metadata.value = await extractDatasetMetadata(file);
        message.success({ content: 'File analyzed successfully', key: 'analyze' });

        // Auto-fill file path with file name (user can edit)
        if (!filePath.value) {
          filePath.value = file.name;
        }
      } catch (error: any) {
        message.error({ content: error.message || 'Failed to analyze file', key: 'analyze' });
      }
    }
  };

  input.click();
};
</script>
