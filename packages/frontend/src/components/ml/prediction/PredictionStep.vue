<template>
  <div class="space-y-6">
    <h2 class="text-2xl font-semibold mb-4">Make Predictions</h2>

    <a-alert
      v-if="selectedModel"
      :message="`Using trained model: ${formatModelName(selectedModel)}`"
      type="success"
      show-icon
      class="mb-4"
    />

    <!-- Mode Selector -->
    <div class="bg-white rounded-lg border p-4">
      <label class="block text-sm font-medium text-gray-700 mb-2">
        Prediction Mode
      </label>
      <a-radio-group v-model:value="predictionMode" button-style="solid">
        <a-radio-button value="file">
          <span class="inline-flex items-center">
            <span class="i-mdi-file-upload mr-2"></span>
            Upload File
          </span>
        </a-radio-button>
        <a-radio-button value="inline">
          <span class="inline-flex items-center">
            <span class="i-mdi-table-edit mr-2"></span>
            Manual Input
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
        <p class="ant-upload-text">Click or drag file to upload</p>
        <p class="ant-upload-hint">
          Upload an Excel or CSV file with the same feature columns
        </p>
      </a-upload-dragger>

      <a-button
        class="mt-4 inline-flex items-center justify-center"
        type="primary"
        size="large"
        block
        :loading="isPredicting"
        :disabled="fileList.length === 0"
        @click="startPredictionFromFile"
      >
        <span class="i-mdi-chart-line mr-2" />
        Start Prediction
      </a-button>
    </div>

    <!-- Inline Input Mode -->
    <div
      v-else-if="predictionMode === 'inline'"
      class="bg-white rounded-lg border p-4"
    >
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-lg font-medium">Manual Data Input</h3>
        <a-button
          type="primary"
          @click="addRow"
          class="inline-flex items-center"
        >
          <span class="i-mdi-plus mr-1" />
          Add Row
        </a-button>
      </div>
      <p class="text-sm text-gray-600 mb-4">
        Enter values for each feature column. You can add multiple rows for
        batch prediction.
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
              @click="removeRow(index)"
              class="inline-flex items-center"
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
        @click="predictInline"
        class="inline-flex items-center justify-center"
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
import { message } from 'ant-design-vue';
import type { UploadProps } from 'ant-design-vue';

import { computed, ref } from 'vue';

import { client } from '../../../api/client';
import { AVAILABLE_MODELS } from '../../../constants/models';
import PredictionResult from './PredictionResult.vue';

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
const predictionMode = ref<'file' | 'inline'>('file');
const fileList = ref<any[]>([]);
const inputData = ref<Record<string, any>[]>([]);
const isPredicting = ref(false);
const predictionTaskId = ref<number | null>(null);

// Computed
const inputColumns = computed(() => {
  const cols: any[] = props.featureColumns.map((col) => ({
    title: col,
    dataIndex: col,
    key: col,
    width: 150,
  }));
  cols.push({
    title: 'Action',
    key: 'action',
    width: 100,
  });
  return cols;
});

/**
 * Format model name for display
 */
const formatModelName = (modelValue: string) => {
  const model = AVAILABLE_MODELS.find((m) => m.value === modelValue);
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
const beforeUpload: UploadProps['beforeUpload'] = (file) => {
  const isExcelOrCsv =
    file.type ===
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
    file.type === 'application/vnd.ms-excel' ||
    file.type === 'text/csv';

  if (!isExcelOrCsv) {
    message.error('You can only upload Excel or CSV files!');
    return false;
  }

  const isLt10M = file.size / 1024 / 1024 < 10;
  if (!isLt10M) {
    message.error('File must be smaller than 10MB!');
    return false;
  }

  return false; // Prevent auto upload
};

/**
 * Start prediction from uploaded file
 */
const startPredictionFromFile = async () => {
  if (fileList.value.length === 0 || !props.selectedModel || !props.taskId) {
    return;
  }

  isPredicting.value = true;
  try {
    throw new Error('File prediction not implemented');
  } catch (error: any) {
    console.error('Prediction failed:', error);
    message.error(error.message || 'Failed to start prediction');
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
      (col) => row[col] === null || row[col] === undefined
    )
  );

  if (hasEmptyFields) {
    message.error('Please fill in all fields');
    return;
  }

  isPredicting.value = true;
  try {
    // Remove the 'key' field from data
    const cleanData = inputData.value.map((row) => {
      const { key, ...rest } = row;
      return rest;
    });

    const response = await client.predict.inline.$post({
      json: {
        predictionData: cleanData,
        model: props.selectedModel,
        tuningTaskId: props.taskId,
        workItemId: props.workItemId,
      },
    });

    message.success('Prediction completed successfully');
    predictionTaskId.value = response.taskId;
  } catch (error: any) {
    console.error('Prediction failed:', error);
    message.error(error.message || 'Failed to predict');
  } finally {
    isPredicting.value = false;
  }
};

/**
 * Reset workflow
 */
const handleReset = () => {
  emit('reset');
};
</script>
