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

    <!-- Mode Selector -->
    <div class="mt-4">
      <label class="block text-sm font-medium text-gray-700 mb-2">
        {{ t("prediction.mode") }}
      </label>
      <a-radio-group v-model:value="predictionMode" button-style="solid">
        <a-radio-button value="file">
          <span class="inline-flex items-center">
            <span class="i-mdi-file-upload mr-2"></span>
            {{ t("prediction.modeFile") }}
          </span>
        </a-radio-button>
        <a-radio-button value="inline">
          <span class="inline-flex items-center">
            <span class="i-mdi-table-edit mr-2"></span>
            {{ t("prediction.modeInline") }}
          </span>
        </a-radio-button>
      </a-radio-group>
    </div>

    <!-- File Upload Mode -->
    <div v-if="predictionMode === 'file'">
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
    </div>

    <!-- Inline Input Mode -->
    <div v-else-if="predictionMode === 'inline'">
      <div class="mt-4">
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-lg font-medium">{{ t("prediction.inlineInput") }}</h3>
          <a-button
            type="primary"
            @click="addRow"
            class="inline-flex items-center"
          >
            <span class="i-mdi-plus mr-1" />
            {{ t("prediction.addRow") }}
          </a-button>
        </div>
        <p class="text-sm text-gray-600 mb-4">
          {{ t("prediction.inlineInputHint") }}
        </p>

        <a-table
          :columns="inputColumns"
          :data-source="inputData"
          :pagination="false"
          bordered
          size="small"
          class="mb-4"
        >
          <template #bodyCell="{ column, record, index }">
            <template v-if="column.key === 'action'">
              <a-button
                type="link"
                danger
                size="small"
                @click="removeRow(index)"
                class="inline-flex items-center"
              >
                <span class="i-mdi-delete mr-1" />
                {{ t("prediction.removeRow") }}
              </a-button>
            </template>
            <template v-else-if="column.key">
              <a-input-number
                v-model:value="record[column.key as string]"
                :placeholder="`Enter ${column.title}`"
                style="width: 100%"
                :precision="4"
              />
            </template>
          </template>
        </a-table>

        <a-button
          type="primary"
          size="large"
          block
          :loading="isPredicting"
          :disabled="inputData.length === 0"
          @click="predictInline"
          class="inline-flex items-center justify-center"
        >
          <span class="i-mdi-chart-line mr-2" />
          {{ t("prediction.predictInline") }}
        </a-button>
      </div>
    </div>

    <div v-if="predictionTask" class="mt-4">
      <PredictionResult
        :task-id="predictionTask.taskId"
        :input-data="predictionMode === 'inline' ? inputData : undefined"
      />
    </div>

    <div class="flex gap-4 mt-6">
      <a-button @click="$emit('back')">{{ t("prediction.back") }}</a-button>
      <a-button @click="handleReset">{{ t("prediction.reset") }}</a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from "vue";
import type { UploadProps } from "ant-design-vue";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";
import { PredictionService, TaskService } from "~/services";
import type { PredictionTask } from "~/types";
import PredictionResult from "./PredictionResult.vue";

const { t } = useI18n();

const props = defineProps<{
  workItemId: number;
  model: string;
  parameters: Record<string, any>;
  taskId: number; // tuningTaskId for backend
  featureColumns: string[];
  targetColumn: string;
}>();

const emit = defineEmits<{
  back: [];
  reset: [];
}>();

// Prediction mode
const predictionMode = ref<"file" | "inline">("file");

// File mode state
const fileList = ref<any[]>([]);

// Inline mode state
const inputData = ref<Record<string, any>[]>([]);

// Shared state
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
        error: predictionTask.value.error || t("common.unknownError"),
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

const inputColumns = computed(() => {
  const cols: any[] = props.featureColumns.map((col) => ({
    title: col,
    dataIndex: col,
    key: col,
  }));
  cols.push({
    title: t("prediction.action"),
    key: "action",
  });
  return cols;
});

/**
 * Add a new row to inline input
 */
const addRow = () => {
  const newRow: Record<string, any> = { key: Date.now() };
  props.featureColumns.forEach((col) => {
    newRow[col] = null;
  });
  inputData.value.push(newRow);
};

/**
 * Remove a row from inline input
 */
const removeRow = (index: number) => {
  inputData.value.splice(index, 1);
};

/**
 * Predict using inline data
 */
const predictInline = async () => {
  if (inputData.value.length === 0) {
    message.error(t("prediction.noInputData"));
    return;
  }

  if (!props.model) {
    message.error(t("messages.selectModelError"));
    return;
  }

  if (!props.taskId) {
    message.error(t("messages.tuningTaskError"));
    return;
  }

  isPredicting.value = true;

  try {
    // Clean up input data - remove key and null values
    const cleanedData = inputData.value.map((row) => {
      const cleanRow: Record<string, any> = {};
      props.featureColumns.forEach((col) => {
        cleanRow[col] = row[col] ?? 0; // Use 0 as default for null values
      });
      return cleanRow;
    });

    const response = await PredictionService.predictInline({
      predictionData: cleanedData,
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

        message.success(t("messages.predictionCompleted"));
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
 * Poll task status until completion
 */
const pollTaskStatus = async (taskId: number, maxAttempts: number = 120) => {
  let attempts = 0;

  while (attempts < maxAttempts) {
    try {
      const response = await TaskService.fetchStatus(taskId);

      if (
        response.task.status === "completed" ||
        response.task.status === "failed"
      ) {
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
 * Reset prediction step state and emit reset event
 */
const resetPrediction = () => {
  fileList.value = [];
  inputData.value = [];
  isPredicting.value = false;
  predictionTask.value = null;
  predictionMode.value = "file";
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
