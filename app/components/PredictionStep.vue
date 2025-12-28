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
        <span
          class="i-mdi-file-table text-6xl text-green-500 inline-block"
        ></span>
      </p>
      <p class="ant-upload-text">{{ t("prediction.uploadData") }}</p>
      <p class="ant-upload-hint">
        {{ t("prediction.uploadHint") }}
      </p>
    </a-upload-dragger>

    <a-button
      class="mt-4 inline-flex items-center justify-center"
      type="primary"
      size="large"
      block
      :loading="isPredicting"
      :disabled="fileList.length === 0"
      @click="startPrediction"
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
import { computed, ref } from "vue";
import type { UploadProps } from "ant-design-vue";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const props = defineProps<{
  bestModel: string | null;
  selectedTaskId: number | null;
  isPredicting: boolean;
  predictionTask: any;
  trainingDatasetId: string;
  featureColumns: string[];
  targetColumn: string;
}>();

const emit = defineEmits<{
  predict: [];
  back: [];
  reset: [];
  "update:isPredicting": [value: boolean];
  "update:predictionTask": [task: any];
}>();

const fileList = defineModel<any[]>({ required: true });

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

// Business logic: Start prediction
const startPrediction = async () => {
  if (!props.selectedTaskId) {
    message.error(t("messages.selectModelError"));
    return;
  }

  if (fileList.value.length === 0) {
    message.error(t("messages.uploadPredictionError"));
    return;
  }

  if (!props.trainingDatasetId) {
    message.error(t("messages.trainingDatasetError"));
    return;
  }

  emit("update:isPredicting", true);

  try {
    // First, fetch the trained parameters from the selected task
    const taskResponse = await $fetch(`/api/results/${props.selectedTaskId}`);
    
    if (!taskResponse.success || !taskResponse.results) {
      message.error("Failed to fetch training results");
      emit("update:isPredicting", false);
      return;
    }

    const trainedParams = taskResponse.results.params;
    
    // Upload prediction dataset
    const file = fileList.value[0].originFileObj;
    const uploadFormData = new FormData();
    uploadFormData.append("file", file);
    uploadFormData.append("name", `Prediction Data - ${new Date().toLocaleString()}`);
    uploadFormData.append("description", "Uploaded for prediction");

    const datasetResponse = await $fetch("/api/data", {
      method: "POST",
      body: uploadFormData,
    });

    if (!datasetResponse.success) {
      message.error("Failed to upload prediction dataset");
      emit("update:isPredicting", false);
      return;
    }

    const predictionDatasetId = datasetResponse.dataset.datasetId;

    // Call simplified predict API
    const formData = new FormData();
    formData.append("model", props.bestModel);
    formData.append("parameters", JSON.stringify(trainedParams));
    formData.append("trainingDatasetId", props.trainingDatasetId);
    formData.append("predictionDatasetId", predictionDatasetId);
    formData.append("featureColumns", JSON.stringify(props.featureColumns));
    formData.append("targetColumn", props.targetColumn);

    const response = await $fetch("/api/predict", {
      method: "POST",
      body: formData,
    });

    if (response.success) {
      emit("update:predictionTask", { taskId: response.taskId, status: "running" });
      message.success(t("messages.predictionStarted"));

      const result = await pollTaskStatus(response.taskId);

      if (result && result.task.status === "completed") {
        const taskResult: any = result.task.result || {};
        const taskParameter: any = result.task.parameter || {};
        emit("update:predictionTask", {
          status: "completed",
          outputFile: taskResult.outputFile || taskParameter.outputFile || response.outputFile,
          taskId: result.task.id,
        });
        message.success(
          t("messages.predictionCompleted", {
            path: taskResult.outputFile || taskParameter.outputFile || response.outputFile,
          })
        );
      } else if (result && result.task.status === "failed") {
        emit("update:predictionTask", {
          status: "failed",
          error: result.task.error,
        });
        message.error(
          t("messages.predictionFailed", { error: result.task.error })
        );
      }
    }
  } catch (error) {
    message.error(t("messages.predictionError") + ": " + error.message);
  } finally {
    emit("update:isPredicting", false);
  }
};

// Poll task status
const pollTaskStatus = async (taskId: number) => {
  const maxAttempts = 120;
  let attempts = 0;

  while (attempts < maxAttempts) {
    try {
      const response = await $fetch(`/api/task/${taskId}`);

      if (response.task.status === "completed" || response.task.status === "failed") {
        return response;
      }

      attempts++;
      if (attempts < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, 5000));
      }
    } catch (error) {
      console.error("Failed to poll task status:", error);
      attempts++;
      if (attempts < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, 5000));
      }
    }
  }

  return null;
};

const downloadResults = () => {
  if (props.predictionTask?.taskId) {
    const downloadUrl = `/api/download/${props.predictionTask.taskId}`;
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = "";
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
