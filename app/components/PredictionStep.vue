<template>
  <div class="space-y-4">
    <h2 class="text-2xl font-semibold mb-4">{{ t("prediction.title") }}</h2>

    <a-alert
      v-if="bestModel"
      :message="t('prediction.bestModel', { model: bestModel })"
      type="success"
      show-icon
    />

    <a-upload-dragger
      class="mt-4"
      v-model:file-list="fileList"
      name="file"
      :before-upload="beforeUpload"
      :max-count="1"
      accept=".xlsx,.xls"
    >
      <p class="ant-upload-drag-icon">
        <i class="i-mdi-file-table text-6xl text-green-500"></i>
      </p>
      <p class="ant-upload-text">{{ t("prediction.uploadData") }}</p>
      <p class="ant-upload-hint">
        {{ t("prediction.uploadHint") }}
      </p>
    </a-upload-dragger>

    <a-button
      class="mt-4"
      type="primary"
      size="large"
      block
      :loading="isPredicting"
      :disabled="fileList.length === 0"
      @click="$emit('predict')"
    >
      <i class="i-mdi-chart-line mr-2"></i>
      {{ t("prediction.startPrediction") }}
    </a-button>

    <div v-if="predictionTask" class="mt-4">
      <a-alert :message="predictionMessage" :type="predictionType" show-icon />

      <a-button
        v-if="predictionTask.status === 'completed' && predictionTask.taskId"
        type="primary"
        size="large"
        block
        class="mt-4"
        @click="downloadResults"
      >
        <i class="i-mdi-download mr-2"></i>
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
import { computed } from "vue";
import type { UploadProps } from "ant-design-vue";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

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
