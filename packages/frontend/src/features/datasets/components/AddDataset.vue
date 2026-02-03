<template>
  <div class="space-y-4">
    <a-form layout="vertical">
      <!-- Storage Type Selector -->
      <a-form-item :label="$t('dataset.add.storageType')" required>
        <a-radio-group v-model:value="storageType" button-style="solid">
          <a-radio-button value="local">
            <span class="inline-flex items-center">
              <span class="i-mdi-harddisk mr-2"></span>
              {{ $t("dataset.add.storageLocal") }}
            </span>
          </a-radio-button>
          <a-radio-button value="oss">
            <span class="inline-flex items-center">
              <span class="i-mdi-cloud mr-2"></span>
              {{ $t("dataset.add.storageOss") }}
            </span>
          </a-radio-button>
        </a-radio-group>
        <div class="text-sm text-gray-500 mt-1">
          <span v-if="storageType === 'local'">
            {{ $t("dataset.add.storageLocalHint") }}
          </span>
          <span v-else>
            {{ $t("dataset.add.storageOssHint") }}
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

      <!-- File Upload (for both local and OSS) -->
      <a-form-item :label="$t('dataset.add.selectFile')" required>
        <a-upload-dragger
          v-model:file-list="fileList"
          :before-upload="beforeUpload"
          accept=".csv,.xlsx,.xls"
          :max-count="1"
          :show-upload-list="{ showRemoveIcon: true }"
          @change="handleFileChange"
        >
          <p class="ant-upload-drag-icon">
            <span
              :class="
                storageType === 'local'
                  ? 'i-mdi-file-document'
                  : 'i-mdi-cloud-upload'
              "
              class="text-4xl text-gray-400"
            ></span>
          </p>
          <p class="ant-upload-text">
            {{ $t("dataset.add.dragDrop") }}
          </p>
          <p class="ant-upload-hint">
            {{ $t("dataset.add.supportedFormats") }}
          </p>
        </a-upload-dragger>
      </a-form-item>

      <!-- Local File Path Input (only for local storage) -->
      <a-form-item
        v-if="storageType === 'local' && fileList.length > 0"
        :label="$t('dataset.add.localFilePath')"
        required
      >
        <a-tooltip
          v-model:open="showPathTooltip"
          placement="top"
          trigger="focus"
        >
          <template #title>
            <div class="p-2 min-w-[600px]">
              <p class="mb-2 text-sm">{{ $t("dataset.add.filePathGuide") }}</p>
              <img
                src="/file-path-guiding.jpg"
                alt="File path guide"
                class="w-full h-auto rounded border"
              />
            </div>
          </template>
          <a-input
            v-model:value="selectedFilePath"
            :placeholder="$t('dataset.add.filePathPlaceholder')"
            @focus="showPathTooltip = true"
            @blur="showPathTooltip = false"
          >
            <template #prefix>
              <span class="i-mdi-folder-open text-gray-400"></span>
            </template>
          </a-input>
        </a-tooltip>
        <div class="text-xs text-gray-500 mt-1">
          {{ $t("dataset.add.filePathHint") }}
        </div>
      </a-form-item>

      <!-- Metadata Display (auto-extracted) -->
      <div v-if="metadata" class="bg-gray-50 p-4 rounded-lg border">
        <h4 class="text-sm font-semibold mb-2">
          {{ $t("dataset.add.datasetInfo") }}
        </h4>
        <div class="space-y-1 text-sm">
          <div>
            <strong>{{ $t("dataset.add.columns") }}:</strong>
            {{ metadata.columns.length }}
          </div>
          <div>
            <strong>{{ $t("dataset.add.rows") }}:</strong>
            {{ metadata.rowCount }}
          </div>
          <div>
            <strong>{{ $t("dataset.add.size") }}:</strong>
            {{ formatFileSize(metadata.fileSize) }}
          </div>
          <!-- Duplicate Detection Info -->
          <div v-if="metadata.duplicateCount && metadata.duplicateCount > 0" class="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded">
            <div class="flex items-center gap-2 text-yellow-800">
              <span class="i-mdi-alert text-lg"></span>
              <strong>{{ $t("dataset.add.duplicatesFound") }}:</strong>
              {{ metadata.duplicateCount }} {{ $t("dataset.add.duplicateRows") }}
            </div>
            <div class="mt-2 text-xs text-yellow-700">
              <div class="font-medium mb-1">{{ $t("dataset.add.affectedRows") }}:</div>
              <div class="font-mono bg-yellow-100 p-2 rounded max-h-20 overflow-y-auto">
                {{ metadata.duplicateRows?.slice(0, 20).join(", ") }}
                <span v-if="(metadata.duplicateRows?.length || 0) > 20">
                  {{ $t("dataset.add.andMore", { count: metadata.duplicateRows!.length - 20 }) }}
                </span>
              </div>
            </div>
            <div class="mt-2 text-xs text-yellow-600">
              {{ $t("dataset.add.duplicateHint") }}
            </div>
          </div>
          <div v-else-if="metadata.duplicateCount === 0" class="mt-3 p-2 bg-green-50 border border-green-200 rounded text-green-700">
            <span class="i-mdi-check-circle mr-1"></span>
            {{ $t("dataset.add.noDuplicates") }}
          </div>
          <div v-if="selectedFilePath" class="mt-2">
            <strong>{{ $t("dataset.add.filePath") }}:</strong>
            <div class="text-xs text-gray-600 mt-1 font-mono break-all">
              {{ selectedFilePath }}
            </div>
          </div>
          <div class="mt-2">
            <strong>{{ $t("dataset.add.columnNames") }}:</strong>
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
        {{ $t("dataset.add.cancel") }}
      </a-button>
      <a-button
        type="primary"
        :loading="creating"
        :disabled="!canCreate"
        @click="
          createDataset(
            (data) => emit('success', data),
            () => {},
          )
        "
      >
        {{
          storageType === "local"
            ? $t("dataset.add.createDataset")
            : $t("dataset.add.uploadAndCreate")
        }}
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from "vue-i18n";

import { useAddDataset } from "@/hooks";

interface Dataset {
  id: number;
  name: string;
  filePath?: string;
  columns: string[];
  createdAt?: string;
}

const props = defineProps<{
  projectId: number;
}>();

const emit = defineEmits<{
  success: [dataset: Dataset];
  cancel: [];
}>();

const { t } = useI18n();

// Use the extracted composable
const {
  storageType,
  datasetName,
  fileList,
  metadata,
  selectedFilePath,
  showPathTooltip,
  canCreate,
  creating,
  formatFileSize,
  beforeUpload,
  handleFileChange,
  handleCreate: createDataset,
} = useAddDataset(props.projectId);
</script>

<style>
.ant-tooltip-inner {
  min-width: fit-content !important;
}
</style>
