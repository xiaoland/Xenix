<template>
  <div class="space-y-4">
    <a-form layout="vertical">
      <!-- Storage Type Selector -->
      <a-form-item :label="$t('dataset.add.storageType')" required>
        <a-radio-group v-model:value="storageType" button-style="solid">
          <a-radio-button value="local">
            <span class="inline-flex items-center">
              <span class="i-mdi-harddisk mr-2"></span>
              {{ $t('dataset.add.storageLocal') }}
            </span>
          </a-radio-button>
          <a-radio-button value="oss">
            <span class="inline-flex items-center">
              <span class="i-mdi-cloud mr-2"></span>
              {{ $t('dataset.add.storageOss') }}
            </span>
          </a-radio-button>
        </a-radio-group>
        <div class="text-sm text-gray-500 mt-1">
          <span v-if="storageType === 'local'">
            {{ $t('dataset.add.storageLocalHint') }}
          </span>
          <span v-else>
            {{ $t('dataset.add.storageOssHint') }}
          </span>
        </div>
      </a-form-item>

      <!-- Dataset Name -->
      <a-form-item :label="$t('dataset.add.name')" required>
        <a-input
          v-model:value="datasetName"
          :placeholder="$t('dataset.add.namePlaceholder')"
        />
      </a-form-item>

      <!-- File Path (for local) or Upload (for OSS) -->
      <a-form-item v-if="storageType === 'local'" :label="$t('dataset.add.filePath')" required>
        <a-input
          v-model:value="filePath"
          :placeholder="$t('dataset.add.filePathPlaceholder')"
        />
        <div class="text-sm text-gray-500 mt-1">
          {{ $t('dataset.add.filePathHint') }}
        </div>
      </a-form-item>

      <a-form-item v-else :label="$t('dataset.add.uploadFile')" required>
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
            {{ $t('dataset.add.dragDrop') }}
          </p>
          <p class="ant-upload-hint">
            {{ $t('dataset.add.supportedFormats') }}
          </p>
        </a-upload-dragger>
      </a-form-item>

      <!-- Metadata Display (auto-extracted) -->
      <div v-if="metadata" class="bg-gray-50 p-4 rounded-lg border">
        <h4 class="text-sm font-semibold mb-2">{{ $t('dataset.add.datasetInfo') }}</h4>
        <div class="space-y-1 text-sm">
          <div><strong>{{ $t('dataset.add.columns') }}:</strong> {{ metadata.columns.length }}</div>
          <div><strong>{{ $t('dataset.add.rows') }}:</strong> {{ metadata.rowCount }}</div>
          <div><strong>{{ $t('dataset.add.size') }}:</strong> {{ formatFileSize(metadata.fileSize) }}</div>
          <div class="mt-2">
            <strong>{{ $t('dataset.add.columnNames') }}:</strong>
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
        {{ $t('dataset.add.cancel') }}
      </a-button>
      <a-button
        type="primary"
        :loading="creating"
        :disabled="!canCreate"
        @click="handleCreate"
      >
        {{ storageType === 'local' ? $t('dataset.add.createDataset') : $t('dataset.add.uploadAndCreate') }}
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { message } from "ant-design-vue";
import type { UploadProps } from "ant-design-vue";

import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";

import { useCreateDataset } from "../../composables";
import { extractDatasetMetadata, type DatasetMetadata } from "../../utils/datasetUtils";

const props = defineProps<{
  projectId: number;
}>();

const emit = defineEmits<{
  success: [];
  cancel: [];
}>();

const { t } = useI18n();

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
    message.error(t('dataset.add.invalidFileFormat'));
    return false;
  }

  const isLt10M = file.size / 1024 / 1024 < 10;
  if (!isLt10M) {
    message.error(t('dataset.add.fileTooLarge'));
    return false;
  }

  return false; // Prevent auto upload
};

const handleFileChange = async () => {
  if (fileList.value.length > 0) {
    try {
      const file = fileList.value[0].originFileObj;
      message.loading({ content: t('dataset.add.analyzingFile'), key: 'analyze' });
      metadata.value = await extractDatasetMetadata(file);
      message.success({ content: t('dataset.add.fileAnalyzed'), key: 'analyze' });
    } catch (error: any) {
      message.error({ content: error.message || t('dataset.add.analyzeFailed'), key: 'analyze' });
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
      message.success(t('dataset.add.createSuccess'));
      emit("success");

      // Reset form
      datasetName.value = "";
      filePath.value = "";
      fileList.value = [];
      metadata.value = null;
    },
    onError: (error: any) => {
      console.error("Creation failed:", error);
      message.error(error.message || t('dataset.add.createFailed'));
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
        message.loading({ content: t('dataset.add.analyzingFile'), key: 'analyze' });
        metadata.value = await extractDatasetMetadata(file);
        message.success({ content: t('dataset.add.fileAnalyzed'), key: 'analyze' });

        // Auto-fill file path with file name (user can edit)
        if (!filePath.value) {
          filePath.value = file.name;
        }
      } catch (error: any) {
        message.error({ content: error.message || t('dataset.add.analyzeFailed'), key: 'analyze' });
      }
    }
  };

  input.click();
};
</script>
