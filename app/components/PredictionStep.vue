<template>
  <div class="space-y-4">
    <h2 class="text-2xl font-semibold mb-4">{{ t("prediction.title") }}</h2>

    <a-alert
      v-if="bestModel"
      :message="t('prediction.bestModel', { model: bestModel })"
      type="success"
      show-icon
    />

    <!-- Input Mode Toggle -->
    <div class="mt-4">
      <a-radio-group v-model:value="inputMode" button-style="solid">
        <a-radio-button value="file">{{ t("prediction.fileMode") }}</a-radio-button>
        <a-radio-button value="manual">{{ t("prediction.manualMode") }}</a-radio-button>
      </a-radio-group>
    </div>

    <!-- File Upload Mode -->
    <a-upload-dragger
      v-if="inputMode === 'file'"
      class="mt-4"
      v-model:file-list="fileList"
      name="file"
      :before-upload="beforeUpload"
      :max-count="1"
      accept=".xlsx,.xls"
    >
      <p class="ant-upload-drag-icon">
        <span
          class="i-mdi-file-table text-6xl text-green-500 inline-block"
        ></span>
      </p>
      <p class="ant-upload-text">{{ t("prediction.uploadData") }}</p>
      <p class="ant-upload-hint">
        {{ t("prediction.uploadHint") }}
      </p>
    </a-upload-dragger>

    <!-- Manual Input Mode -->
    <div v-if="inputMode === 'manual'" class="mt-4">
      <a-alert
        :message="t('prediction.manualInputHint')"
        type="info"
        show-icon
        class="mb-4"
      />
      <a-form layout="vertical">
        <a-form-item
          v-for="feature in featureColumns"
          :key="feature"
          :label="feature"
        >
          <a-input-number
            v-model:value="manualInputValues[feature]"
            :placeholder="t('prediction.enterValue')"
            class="w-full"
          />
        </a-form-item>
      </a-form>
    </div>

    <a-button
      class="mt-4 inline-flex items-center justify-center"
      type="primary"
      size="large"
      block
      :loading="isPredicting"
      :disabled="!canPredict"
      @click="$emit('predict', { inputMode, manualInputValues: manualInputValues })"
    >
      <span class="i-mdi-chart-line mr-2" />
      {{ t("prediction.startPrediction") }}
    </a-button>

    <div v-if="predictionTask" class="mt-4">
      <a-alert :message="predictionMessage" :type="predictionType" show-icon />

      <a-button
        v-if="predictionTask.status === 'completed' && predictionTask.taskId"
        type="primary"
        size="large"
        block
        class="mt-4 inline-flex items-center justify-center"
        @click="downloadResults"
      >
        <span class="i-mdi-download mr-2" />
        {{ t("prediction.downloadResults") }}
      </a-button>
    </div>

    <div class="flex gap-4 mt-6">
      <a-button @click="$emit('back')">{{ t("prediction.back") }}</a-button>
      <a-button @click="$emit('reset')">{{ t("prediction.reset") }}</a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { UploadProps } from "ant-design-vue";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const props = defineProps<{
  bestModel: string | null;
  isPredicting: boolean;
  predictionTask: any;
  featureColumns: string[];
}>();

const fileList = defineModel<any[]>({ required: true });

defineEmits<{
  predict: [payload: { inputMode: string; manualInputValues: Record<string, number> }];
  back: [];
  reset: [];
}>();

const inputMode = ref<"file" | "manual">("file");
const manualInputValues = ref<Record<string, number>>({});

// Initialize manual input values when feature columns change
watch(() => props.featureColumns, (features) => {
  if (features && features.length > 0) {
    const initialValues: Record<string, number> = {};
    features.forEach(feature => {
      initialValues[feature] = 0;
    });
    manualInputValues.value = initialValues;
  }
}, { immediate: true });

const canPredict = computed(() => {
  if (inputMode.value === "file") {
    return fileList.value.length > 0;
  } else {
    // Check if all manual input values are provided
    return props.featureColumns.every(feature => 
      manualInputValues.value[feature] !== undefined && 
      manualInputValues.value[feature] !== null
    );
  }
});

const predictionMessage = computed(() => {
  if (!props.predictionTask) return "";

  switch (props.predictionTask.status) {
    case "pending":
      return t("prediction.taskQueued");
    case "running":
      return t("prediction.generating");
    case "completed":
      return t("prediction.completed");
    case "failed":
      return t("prediction.failed", {
        error: props.predictionTask.error || "Unknown error",
      });
    default:
      return "";
  }
});

const predictionType = computed(() => {
  if (!props.predictionTask) return "info";

  switch (props.predictionTask.status) {
    case "completed":
      return "success";
    case "failed":
      return "error";
    default:
      return "info";
  }
});

const beforeUpload: UploadProps["beforeUpload"] = (file) => {
  const isExcel = file.name.endsWith(".xlsx") || file.name.endsWith(".xls");
  if (!isExcel) {
    message.error(t("prediction.excelOnly"));
  }
  return false; // Prevent auto upload
};

const downloadResults = () => {
  if (props.predictionTask?.taskId) {
    // Use the download API endpoint
    const downloadUrl = `/api/download/${props.predictionTask.taskId}`;

    // Create a link element and trigger download
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = ""; // Let the server specify the filename
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    message.success(t("prediction.downloading"));
  }
};
</script>

<style scoped>
.ant-upload-drag-icon {
  margin-bottom: 1rem;
}
</style>
