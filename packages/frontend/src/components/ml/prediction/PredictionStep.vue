<template>
  <div class="space-y-6">
    <h2 class="text-2xl font-semibold mb-4">
      {{ $t("ml.prediction.title") }}
    </h2>

    <a-alert
      v-if="selectedModel"
      :message="
        $t('ml.prediction.usingModel', {
          model: formatModelName(selectedModel),
        })
      "
      type="success"
      show-icon
      class="mb-4"
    />

    <!-- Mode Selector -->
    <div class="bg-white rounded-lg border p-4">
      <label class="block text-sm font-medium text-gray-700 mb-2">
        {{ $t("ml.prediction.mode") }}
      </label>
      <a-radio-group v-model:value="predictionMode" button-style="solid">
        <a-radio-button value="file">
          <span class="inline-flex items-center">
            <span class="i-mdi-file-upload mr-2"></span>
            {{ $t("ml.prediction.uploadFile") }}
          </span>
        </a-radio-button>
        <a-radio-button value="inline">
          <span class="inline-flex items-center">
            <span class="i-mdi-table-edit mr-2"></span>
            {{ $t("ml.prediction.manualInput") }}
          </span>
        </a-radio-button>
      </a-radio-group>
    </div>

    <!-- File Upload Mode -->
    <div
      v-if="predictionMode === 'file'"
      class="bg-white rounded-lg border p-4"
    >
      <h3 class="text-lg font-medium mb-3">Upload Prediction Data</h3>

      <!-- For OSS storage: File Upload -->
      <template v-if="storageType === 'oss'">
        <a-upload-dragger
          v-model:file-list="fileList"
          name="file"
          :before-upload="beforeUpload"
          :max-count="1"
          accept=".xlsx,.xls,.csv"
        >
          <p class="ant-upload-drag-icon">
            <span
              class="i-mdi-file-table text-6xl text-green-500 inline-block"
            ></span>
          </p>
          <p class="ant-upload-text">
            {{ $t("ml.prediction.dragHint") }}
          </p>
          <p class="ant-upload-hint">
            {{ $t("ml.prediction.supportedFormats") }}
          </p>
        </a-upload-dragger>
      </template>

      <!-- For Local storage: File Path Input -->
      <template v-else-if="storageType === 'local'">
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              Select Prediction File
            </label>
            <a-upload-dragger
              v-model:file-list="fileList"
              name="file"
              :before-upload="beforeUpload"
              :max-count="1"
              accept=".xlsx,.xls,.csv"
              :show-upload-list="false"
              @change="handleFileChange"
            >
              <p class="ant-upload-drag-icon">
                <span
                  class="i-mdi-file-document text-6xl text-blue-500 inline-block"
                ></span>
              </p>
              <p class="ant-upload-text">Select prediction file</p>
              <p class="ant-upload-hint">
                {{ $t("ml.prediction.supportedFormats") }}
              </p>
            </a-upload-dragger>
          </div>

          <div v-if="fileList.length > 0">
            <label class="block text-sm font-medium text-gray-700 mb-2">
              File Path
            </label>
            <a-tooltip
              v-model:open="showPathTooltip"
              placement="top"
              trigger="focus"
            >
              <template #title>
                <div class="p-2 min-w-[600px]">
                  <p class="mb-2 text-sm">
                    {{ $t("dataset.add.filePathGuide") }}
                  </p>
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
                class="mb-2"
              />
            </a-tooltip>
            <div class="text-xs text-gray-500">
              Selected file: {{ fileList[0]?.name }}
            </div>
          </div>
        </div>
      </template>

      <a-button
        class="mt-4 inline-flex items-center justify-center"
        type="primary"
        size="large"
        block
        :loading="isPredicting"
        :disabled="
          (storageType === 'oss' && fileList.length === 0) ||
          (storageType === 'local' &&
            (fileList.length === 0 ||
              !selectedFilePath.trim() ||
              !predictionMetadata))
        "
        @click="startPredictionFromFile"
      >
        <span class="i-mdi-chart-line mr-2" />
        {{ $t("ml.prediction.startPrediction") }}
      </a-button>
    </div>

    <!-- Inline Input Mode -->
    <div
      v-else-if="predictionMode === 'inline'"
      class="bg-white rounded-lg border p-4"
    >
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-lg font-medium">
          {{ $t("ml.prediction.enterData") }}
        </h3>
        <a-button
          type="primary"
          class="inline-flex items-center"
          @click="addRow"
        >
          <span class="i-mdi-plus mr-1" />
          {{ $t("common.add") }}
        </a-button>
      </div>
      <p class="text-sm text-gray-600 mb-4">
        {{ $t("ml.prediction.inputHint") }}
      </p>

      <a-table
        v-if="inputData.length > 0"
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
              class="inline-flex items-center"
              @click="removeRow(index)"
            >
              <span class="i-mdi-delete mr-1" />
              Remove
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

      <div v-else class="text-center py-8 text-gray-500">
        No rows added. Click "Add Row" to start entering data.
      </div>

      <a-button
        type="primary"
        size="large"
        block
        :loading="isPredicting"
        :disabled="inputData.length === 0"
        class="inline-flex items-center justify-center"
        @click="predictInline"
      >
        <span class="i-mdi-chart-line mr-2" />
        Predict
      </a-button>
    </div>

    <!-- Prediction Result -->
    <div v-if="predictionTaskId" class="bg-white rounded-lg border p-4">
      <h3 class="text-lg font-medium mb-3">Prediction Result</h3>
      <PredictionResult
        :task-id="predictionTaskId"
        :work-item-id="workItemId"
      />
    </div>

    <!-- Navigation -->
    <div class="flex justify-between">
      <a-button @click="emit('back')"> Back to Tuning </a-button>
      <a-button @click="handleReset"> Reset Workflow </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { message } from "ant-design-vue";
import type { UploadProps } from "ant-design-vue";

import { computed, ref } from "vue";

import { client } from "../../../api/client";
import { useModels, useWorkItem, useMLBackendDeployments } from "@/composables";
import { API_CONFIG } from "../../../constants/config";
import { extractDatasetMetadata } from "../../../utils/datasetUtils";
import PredictionResult from "./PredictionResult.vue";

const props = defineProps<{
  workItemId: number;
  selectedModel: string | null;
  selectedParameters: Record<string, any>;
  taskId: number | null;
  featureColumns: string[];
}>();

const emit = defineEmits<{
  back: [];
  reset: [];
}>();

// State
const predictionMode = ref<"file" | "inline">("file");
const fileList = ref<any[]>([]);
const selectedFilePath = ref("");
const inputData = ref<Record<string, any>[]>([]);
const isPredicting = ref(false);
const predictionTaskId = ref<number | null>(null);
const predictionMetadata = ref<any>(null);
const showPathTooltip = ref(false);

// Computed
const inputColumns = computed(() => {
  const cols: any[] = props.featureColumns.map((col) => ({
    title: col,
    dataIndex: col,
    key: col,
    width: 150,
  }));
  cols.push({
    title: "Action",
    key: "action",
    width: 100,
  });
  return cols;
});

// Fetch available models from backend
const { data: availableModels } = useModels();

// Fetch work item details
const { data: workItem } = useWorkItem(props.workItemId);

// Fetch ML backend deployments
const { data: deployments } = useMLBackendDeployments();

// Computed
const storageType = computed(() => {
  if (!workItem.value?.mlBackendDeploymentId || !deployments.value) return null;
  const deployment = deployments.value.find(
    (d) => d.id === workItem.value.mlBackendDeploymentId,
  );
  return deployment?.storage || null;
});

/**
 * Format model name for display
 */
const formatModelName = (modelValue: string) => {
  const model = availableModels.value?.find((m) => m.value === modelValue);
  return model ? model.label : modelValue;
};

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
 * Before upload handler
 */
const beforeUpload: UploadProps["beforeUpload"] = (file) => {
  const isExcelOrCsv =
    file.type ===
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
    file.type === "application/vnd.ms-excel" ||
    file.type === "text/csv";

  if (!isExcelOrCsv) {
    message.error("You can only upload Excel or CSV files!");
    return false;
  }

  const isLt10M = file.size / 1024 / 1024 < 10;
  if (!isLt10M) {
    message.error("File must be smaller than 10MB!");
    return false;
  }

  return false; // Prevent auto upload
};

/**
 * Handle file change for metadata extraction
 */
const handleFileChange = async () => {
  if (fileList.value.length > 0 && storageType.value === "local") {
    try {
      const file = fileList.value[0].originFileObj;
      message.loading({
        content: "Analyzing prediction file...",
        key: "analyze",
      });

      // Extract metadata from the file
      predictionMetadata.value = await extractDatasetMetadata(file);

      message.success({
        content: "File analyzed successfully",
        key: "analyze",
      });
    } catch (error: any) {
      message.error({
        content: error.message || "Failed to analyze file",
        key: "analyze",
      });
      predictionMetadata.value = null;
    }
  } else {
    predictionMetadata.value = null;
  }
};

/**
 * Start prediction from uploaded file
 */
const startPredictionFromFile = async () => {
  if (!props.selectedModel || !props.taskId) {
    return;
  }

  // For OSS: require file upload
  // For local: require file selection, file path, and metadata
  if (
    (storageType.value === "oss" && fileList.value.length === 0) ||
    (storageType.value === "local" &&
      (fileList.value.length === 0 ||
        !selectedFilePath.value.trim() ||
        !predictionMetadata.value))
  ) {
    return;
  }

  isPredicting.value = true;
  try {
    const file = fileList.value[0]?.originFileObj;

    // Create FormData
    const formData = new FormData();
    formData.append("workItemId", String(props.workItemId));
    formData.append("model", props.selectedModel);
    formData.append("tuningTaskId", String(props.taskId));

    if (storageType.value === "oss") {
      // For OSS: upload the file
      if (!file) {
        throw new Error("No file selected");
      }
      formData.append("file", file);
    } else {
      // For local: send file path and metadata
      const filePath = `${selectedFilePath.value.trim()}/${fileList.value[0].name}`;
      formData.append("filePath", filePath);
      formData.append("fileName", fileList.value[0].name);
      formData.append(
        "fileSize",
        String(predictionMetadata.value?.fileSize || 0),
      );
      formData.append(
        "columns",
        JSON.stringify(predictionMetadata.value?.columns || []),
      );
      formData.append(
        "rowCount",
        String(predictionMetadata.value?.rowCount || 0),
      );
    }

    // Use fetch directly for FormData to ensure proper Content-Type with boundary
    const token = localStorage.getItem("auth_token");
    const apiUrl = import.meta.env.VITE_API_URL || API_CONFIG.DEFAULT_URL;

    const response = await fetch(
      `${apiUrl}/work-items/${props.workItemId}/predict/file`,
      {
        method: "POST",
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          // Don't set Content-Type - let browser set it with boundary
        },
        body: formData,
      },
    );

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.message || "Failed to start prediction");
    }

    const data = await response.json();
    message.success("File prediction started successfully");
    predictionTaskId.value = data.taskId;
  } catch (error: any) {
    console.error("Prediction failed:", error);
    message.error(error.message || "Failed to start prediction");
  } finally {
    isPredicting.value = false;
  }
};

/**
 * Predict with inline data
 */
const predictInline = async () => {
  if (inputData.value.length === 0 || !props.selectedModel || !props.taskId) {
    return;
  }

  // Validate that all fields are filled
  const hasEmptyFields = inputData.value.some((row) =>
    props.featureColumns.some(
      (col) => row[col] === null || row[col] === undefined,
    ),
  );

  if (hasEmptyFields) {
    message.error("Please fill in all fields");
    return;
  }

  isPredicting.value = true;
  try {
    // Remove the 'key' field from data
    const cleanData = inputData.value.map((row) => {
      const { key: _key, ...rest } = row;
      return rest;
    });

    const response = await client["work-items"][":id"]["predict"][
      "inline"
    ].$post({
      param: { id: String(props.workItemId) },
      json: {
        predictionData: cleanData,
        model: props.selectedModel,
        tuningTaskId: props.taskId,
        workItemId: props.workItemId,
      },
    });

    const data = await response.json();
    message.success("Prediction completed successfully");
    predictionTaskId.value = data.taskId;
  } catch (error: any) {
    console.error("Prediction failed:", error);
    message.error(error.message || "Failed to predict");
  } finally {
    isPredicting.value = false;
  }
};

/**
 * Reset workflow
 */
const handleReset = () => {
  emit("reset");
};
</script>
<style>
.ant-tooltip-inner {
  min-width: fit-content !important;
}
</style>
