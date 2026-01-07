<template>
  <div class="space-y-4">
    <h2 class="text-2xl font-semibold mb-4">{{ $t("upload.title") }}</h2>

    <!-- File Upload Section -->
    <div class="flex flex-col gap-4">
      <!-- New Dataset Form -->
      <a-form layout="vertical">
        <a-form-item :label="$t('datasets.name')" required>
          <a-input
            v-model:value="newDatasetName"
            :placeholder="$t('datasets.namePlaceholder')"
          />
        </a-form-item>

        <a-form-item :label="$t('datasets.description')">
          <a-textarea
            v-model:value="newDatasetDescription"
            :placeholder="$t('datasets.descriptionPlaceholder')"
            :rows="2"
          />
        </a-form-item>

        <a-form-item :label="$t('datasets.file')" required>
          <a-upload-dragger
            v-model:file-list="fileList"
            name="file"
            :before-upload="beforeUpload"
            :max-count="1"
            accept=".xlsx,.xls"
          >
            <p class="ant-upload-drag-icon">
              <span
                class="i-mdi-cloud-upload text-6xl text-blue-500 inline-block"
              ></span>
            </p>
            <p class="ant-upload-text">{{ $t("upload.dragHint") }}</p>
            <p class="ant-upload-hint">
              {{ $t("upload.hint") }}
            </p>
          </a-upload-dragger>
        </a-form-item>
      </a-form>

      <a-button
        type="primary"
        size="large"
        block
        :disabled="isProcessing || fileList.length === 0 || !newDatasetName"
        :loading="isProcessing"
        @click="handleContinue"
      >
        {{ $t("upload.nextButton") }}
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";
import type { UploadProps } from "ant-design-vue";
import { useFileUpload } from "~/composables/useFileUpload";
import type { Dataset } from "~/types";

const { t } = useI18n();
const { validateExcelFile } = useFileUpload();

const props = defineProps<{
  projectId?: number;
}>();

const emit = defineEmits<{
  datasetUploaded: [
    {
      datasetId: number;
      columns: string[];
    }
  ];
}>();

// State
const fileList = ref<any[]>([]);
const newDatasetName = ref("");
const newDatasetDescription = ref("");
const isProcessing = ref(false);

/**
 * Validate file before upload
 */
const beforeUpload: UploadProps["beforeUpload"] = (file) => {
  if (!validateExcelFile(file)) {
    return false;
  }
  return false; // Prevent auto upload
};

/**
 * Upload new dataset to server
 */
const uploadNewDataset = async () => {
  if (!newDatasetName.value || fileList.value.length === 0) {
    message.error(t("upload.noFileError"));
    return null;
  }

  const formData = new FormData();
  formData.append("file", fileList.value[0].originFileObj);
  formData.append("name", newDatasetName.value);
  if (newDatasetDescription.value) {
    formData.append("description", newDatasetDescription.value);
  }
  if (props.projectId) {
    formData.append("projectId", String(props.projectId));
  }

  try {
    const response = await $fetch("/api/data", {
      method: "POST",
      body: formData,
    });

    if (response.success) {
      message.success(t("datasets.uploadSuccess"));
      return response.dataset as unknown as Dataset;
    }
  } catch (error) {
    console.error("Failed to upload dataset:", error);
    message.error(t("datasets.uploadError"));
    return null;
  }
};

/**
 * Handle continue button click
 */
const handleContinue = async () => {
  isProcessing.value = true;
  try {
    let dataset: Dataset | null = null;

    // Upload new dataset
    dataset = (await uploadNewDataset()) || null;

    if (dataset) {
      emit("datasetUploaded", {
        datasetId: dataset.id,
        columns: dataset.columns || [],
      });

      // Reset form
      fileList.value = [];
      newDatasetName.value = "";
      newDatasetDescription.value = "";
    }
  } finally {
    isProcessing.value = false;
  }
};

onMounted(() => {
  // No dataset fetching needed anymore
});
</script>

<style scoped>
.ant-upload-drag-icon {
  margin-bottom: 1rem;
}
</style>
