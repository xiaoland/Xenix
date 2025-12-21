<template>
  <div class="space-y-4">
    <h2 class="text-2xl font-semibold mb-4">{{ $t("upload.title") }}</h2>

    <!-- File Upload Section -->
    <div v-if="!showColumnSelection" class="flex flex-col gap-4">
      <a-upload-dragger
        v-model:file-list="fileList"
        name="file"
        :before-upload="beforeUpload"
        :max-count="1"
        accept=".xlsx,.xls"
      >
        <p class="ant-upload-drag-icon">
          <i class="i-mdi-cloud-upload text-6xl text-blue-500"></i>
        </p>
        <p class="ant-upload-text">{{ $t("upload.dragHint") }}</p>
        <p class="ant-upload-hint">
          {{ $t("upload.hint") }}
        </p>
      </a-upload-dragger>

      <a-button
        type="primary"
        size="large"
        block
        :disabled="fileList.length === 0"
        :loading="isLoadingColumns"
        @click="handleFileUploaded"
      >
        {{ $t("upload.nextButton") }}
      </a-button>
    </div>

    <!-- Column Selection Section -->
    <ColumnSelector
      v-else
      :columns="excelColumns"
      :feature-columns="selectedFeatureColumns"
      :target-column="selectedTargetColumn"
      @back="handleBackToUpload"
      @confirm="handleColumnSelection"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import type { UploadProps } from "ant-design-vue";
import { message } from "ant-design-vue";
import * as XLSX from "xlsx";

const fileList = defineModel<any[]>({ required: true });

const emit = defineEmits<{
  continue: [{ featureColumns: string[]; targetColumn: string }];
}>();

const showColumnSelection = ref(false);
const isLoadingColumns = ref(false);
const excelColumns = ref<string[]>([]);
const selectedFeatureColumns = ref<string[]>([]);
const selectedTargetColumn = ref<string | undefined>(undefined);

const beforeUpload: UploadProps["beforeUpload"] = (file) => {
  const isExcel = file.name.endsWith(".xlsx") || file.name.endsWith(".xls");
  if (!isExcel) {
    message.error("You can only upload Excel files!");
  }
  return false; // Prevent auto upload
};

const handleFileUploaded = async () => {
  if (fileList.value.length === 0) {
    message.error("Please upload a file first");
    return;
  }

  isLoadingColumns.value = true;

  try {
    // Read the Excel file to extract column names
    const file = fileList.value[0].originFileObj;
    const arrayBuffer = await file.arrayBuffer();
    const workbook = XLSX.read(arrayBuffer, { type: "array" });

    // Get the first sheet
    const firstSheetName = workbook.SheetNames[0];
    const worksheet = workbook.Sheets[firstSheetName];

    // Convert to JSON to get column names
    const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });

    if (jsonData.length === 0) {
      message.error("The Excel file appears to be empty");
      return;
    }

    // First row contains column names
    const columns = (jsonData[0] as any[]).filter(
      (col) => col !== null && col !== undefined && col !== ""
    );

    if (columns.length === 0) {
      message.error("No column headers found in the Excel file");
      return;
    }

    excelColumns.value = columns.map(String);
    showColumnSelection.value = true;

    message.success(`Found ${columns.length} columns in the Excel file`);
  } catch (error) {
    console.error("Error reading Excel file:", error);
    message.error(
      "Failed to read Excel file. Please make sure it has a valid format."
    );
  } finally {
    isLoadingColumns.value = false;
  }
};

const handleBackToUpload = () => {
  showColumnSelection.value = false;
  selectedFeatureColumns.value = [];
  selectedTargetColumn.value = undefined;
};

const handleColumnSelection = ({
  featureColumns,
  targetColumn,
}: {
  featureColumns: string[];
  targetColumn: string;
}) => {
  selectedFeatureColumns.value = featureColumns;
  selectedTargetColumn.value = targetColumn;

  message.success(
    `Selected ${featureColumns.length} feature columns and 1 target column`
  );

  // Emit the selection to parent
  emit("continue", { featureColumns, targetColumn });
};
</script>

<style scoped>
.ant-upload-drag-icon {
  margin-bottom: 1rem;
}
</style>
