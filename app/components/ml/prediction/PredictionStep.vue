<template>
  <div class="space-y-4">
    <h2 class="text-2xl font-semibold mb-4">{{ t("prediction.title") }}</h2>

    <a-alert
      v-if="model"
      :message="
        t('prediction.bestModel', {
          model: t(`models.${model.replace('.', '_')}`),
        })
      "
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

      <!-- Task Logs -->
      <div class="mt-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm font-medium text-gray-700">{{
            t("logs.title")
          }}</span>
          <a-button
            size="small"
            @click="fetchTaskLogs"
            class="inline-flex items-center"
          >
            <span class="i-mdi-refresh mr-1" />
            {{ t("common.refresh") }}
          </a-button>
        </div>
        <LogPanel :logs="taskLogs" />
      </div>

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
      <a-button @click="handleReset">{{ t("prediction.reset") }}</a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import type { UploadProps } from "ant-design-vue";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";
import { PredictionService } from "~/services";
import { useTaskPolling } from "~/composables/useTaskPolling";
import type { PredictionTask } from "~/types";

const { t } = useI18n();
const { pollTaskStatus } = useTaskPolling();

const props = defineProps<{
  workItemId: number;
  model: string;
  parameters: Record<string, any>;
  taskId: number; // tuningTaskId for backend
}>();

const emit = defineEmits<{
  back: [];
  reset: [];
}>();

// Internal state (moved from usePredictionStep composable)
const fileList = ref<any[]>([]);
const isPredicting = ref(false);
const predictionTask = ref<PredictionTask | null>(null);

// Computed properties for task status display
const predictionMessage = computed(() => {
  if (!predictionTask.value) return "";

  switch (predictionTask.value.status) {
    case "pending":
      return t("prediction.taskQueued");
    case "running":
      return t("prediction.generating");
    case "completed":
      return t("prediction.completed");
    case "failed":
      return t("prediction.failed", {
        error: predictionTask.value.error || "Unknown error",
      });
    default:
      return "";
  }
});

const predictionType = computed(() => {
  if (!predictionTask.value) return "info";

  switch (predictionTask.value.status) {
    case "completed":
      return "success";
    case "failed":
      return "error";
    default:
      return "info";
  }
});

/**
 * Validate file before upload
 */
const beforeUpload: UploadProps["beforeUpload"] = (file) => {
  const isExcel = file.name.endsWith(".xlsx") || file.name.endsWith(".xls");
  if (!isExcel) {
    message.error(t("prediction.excelOnly"));
  }
  return false; // Prevent auto upload
};

/**
 * Start prediction with uploaded file
 * Backend fetches trainingDatasetId, featureColumns, targetColumn from workItemId
 */
const startPrediction = async () => {
  if (!props.model) {
    message.error(t("messages.selectModelError"));
    return;
  }

  if (fileList.value.length === 0) {
    message.error(t("messages.uploadPredictionError"));
    return;
  }

  if (!props.taskId) {
    message.error(t("messages.tuningTaskError"));
    return;
  }

  isPredicting.value = true;

  try {
    const response = await PredictionService.start({
      file: fileList.value[0].originFileObj,
      model: props.model,
      tuningTaskId: props.taskId,
      workItemId: props.workItemId,
    });

    if (response.success) {
      predictionTask.value = { taskId: response.taskId, status: "running" };
      message.success(t("messages.predictionStarted"));

      const result = await pollTaskStatus(response.taskId);

      if (result && result.task.status === "completed") {
        predictionTask.value.status = "completed";
        const taskResult: any = result.task.result || {};
        const taskParameter: any = result.task.parameter || {};
        predictionTask.value.outputFile =
          taskResult.outputFile ||
          taskParameter.outputFile ||
          response.outputFile;
        predictionTask.value.taskId = result.task.id;
        message.success(
          t("messages.predictionCompleted", {
            path: predictionTask.value.outputFile,
          })
        );
      } else if (result && result.task.status === "failed") {
        predictionTask.value.status = "failed";
        predictionTask.value.error = result.task.error;
        message.error(
          t("messages.predictionFailed", { error: result.task.error })
        );
      }
    }
  } catch (error: any) {
    message.error(t("messages.predictionError") + ": " + error.message);
  } finally {
    isPredicting.value = false;
  }
};

/**
 * Download prediction results
 */
const downloadResults = () => {
  if (predictionTask.value?.taskId) {
    const downloadUrl = `/api/download/${predictionTask.value.taskId}`;
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = "";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    message.success(t("prediction.downloading"));
  }
};

/**
 * Reset prediction step state and emit reset event
 */
const resetPrediction = () => {
  fileList.value = [];
  isPredicting.value = false;
  predictionTask.value = null;
};

const handleReset = () => {
  resetPrediction();
  emit("reset");
};
</script>

<style scoped>
.ant-upload-drag-icon {
  margin-bottom: 1rem;
}
</style>
