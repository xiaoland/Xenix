<template>
  <div class="space-y-4">
    <h2 class="text-2xl font-semibold mb-4">{{ $t("upload.title") }}</h2>

    <!-- File Upload Section -->
    <div v-if="!showColumnSelection" class="flex flex-col gap-4">
      <!-- Dataset Selection -->
      <a-card :title="$t('datasets.useExistingDataset')" class="mb-4">
        <a-select
          v-model:value="selectedDatasetId"
          :placeholder="$t('datasets.selectDatasetPlaceholder')"
          size="large"
          style="width: 100%"
          :loading="isLoadingDatasets"
          show-search
          :filter-option="filterDatasetOption"
          @change="handleDatasetSelected"
        >
          <a-select-option
            v-for="dataset in datasets"
            :key="dataset.datasetId"
            :value="dataset.datasetId"
          >
            <div class="flex justify-between items-center">
              <span>{{ dataset.name }}</span>
              <a-tag color="blue" class="ml-2"
                >{{ dataset.rowCount }} {{ $t("datasets.rows") }}</a-tag
              >
            </div>
          </a-select-option>
        </a-select>
      </a-card>

      <!-- Divider -->
      <a-divider>{{ $t("datasets.orUploadNew") }}</a-divider>

      <!-- File Upload -->
      <a-upload-dragger
        v-model:file-list="fileList"
        name="file"
        :before-upload="beforeUpload"
        :max-count="1"
        accept=".xlsx,.xls"
        :disabled="!!selectedDatasetId"
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

      <a-button
        type="primary"
        size="large"
        block
        :disabled="!selectedDatasetId && fileList.length === 0"
        :loading="isLoadingColumns"
        @click="handleContinue"
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
import { ref, onMounted } from "vue";
import type { UploadProps } from "ant-design-vue";
import { message } from "ant-design-vue";
import * as XLSX from "xlsx";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const fileList = defineModel<any[]>({ required: true });

const emit = defineEmits<{
  continue: [
    {
      featureColumns: string[];
      targetColumn: string;
      datasetId?: string;
    }
  ];
}>();

interface Dataset {
  id: number;
  datasetId: string;
  name: string;
  description?: string;
  fileName: string;
  fileSize: number;
  columns: string[];
  rowCount: number;
  createdAt: string;
}

const datasets = ref<Dataset[]>([]);
const isLoadingDatasets = ref(false);
const selectedDatasetId = ref<string | undefined>(undefined);
const selectedDataset = ref<Dataset | null>(null);

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
  // Clear dataset selection if uploading file
  selectedDatasetId.value = undefined;
  selectedDataset.value = null;
  return false; // Prevent auto upload
};

const fetchDatasets = async () => {
  isLoadingDatasets.value = true;
  try {
    const response = await $fetch("/api/data");
    if (response.success) {
      datasets.value = response.datasets;
    }
  } catch (error) {
    console.error("Failed to fetch datasets:", error);
  } finally {
    isLoadingDatasets.value = false;
  }
};

const filterDatasetOption = (input: string, option: any) => {
  const dataset = datasets.value.find((d) => d.datasetId === option.value);
  if (!dataset) return false;
  return dataset.name.toLowerCase().includes(input.toLowerCase());
};

const handleDatasetSelected = (datasetId: string) => {
  selectedDataset.value =
    datasets.value.find((d) => d.datasetId === datasetId) || null;
  // Clear file upload if dataset is selected
  fileList.value = [];
};

const handleContinue = async () => {
  if (selectedDatasetId.value) {
    // Use selected dataset
    await handleDatasetContinue();
  } else if (fileList.value.length > 0) {
    // Use uploaded file
    await handleFileUploaded();
  } else {
    message.error("Please select a dataset or upload a file");
  }
};

const handleDatasetContinue = async () => {
  if (!selectedDataset.value) {
    message.error("Please select a dataset");
    return;
  }

  isLoadingColumns.value = true;
  try {
    excelColumns.value = selectedDataset.value.columns;
    showColumnSelection.value = true;
    message.success(
      `Found ${selectedDataset.value.columns.length} columns in the dataset`
    );
  } catch (error) {
    console.error("Error loading dataset columns:", error);
    message.error("Failed to load dataset columns");
  } finally {
    isLoadingColumns.value = false;
  }
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

  // Emit the selection to parent, including datasetId if using existing dataset
  emit("continue", {
    featureColumns,
    targetColumn,
    datasetId: selectedDatasetId.value,
  });
};

onMounted(() => {
  fetchDatasets();
});
</script>

<style scoped>
.ant-upload-drag-icon {
  margin-bottom: 1rem;
}
</style>
