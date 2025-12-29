<template>
  <div class="space-y-4">
    <h2 class="text-2xl font-semibold mb-4">{{ $t("upload.title") }}</h2>

    <!-- File Upload Section -->
    <div v-if="!showColumnSelection" class="flex flex-col gap-4">
      <!-- Dataset Selection -->
      <a-card :title="$t('datasets.useExistingDataset')" class="mb-4">
        <ClientOnly>
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
              :key="dataset.id"
              :value="dataset.id"
            >
              <div class="flex justify-between items-center">
                <span>{{ dataset.name }}</span>
                <a-tag color="blue" class="ml-2"
                  >{{ dataset.rowCount }} {{ $t("datasets.rows") }}</a-tag
                >
              </div>
            </a-select-option>
          </a-select>
        </ClientOnly>
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
import { ref, onMounted, watch } from "vue";
import type { UploadProps } from "ant-design-vue";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";
import { useFileUpload } from "../composables/useFileUpload";
import { DatasetService } from "../services";
import type { Dataset, Project } from "../types";

const { t } = useI18n();
const { isLoadingColumns, readExcelColumns, validateExcelFile } = useFileUpload();

const fileList = defineModel<any[]>({ required: true });

const props = defineProps<{
  projectId?: number;
}>();

const emit = defineEmits<{
  continue: [
    {
      featureColumns: string[];
      targetColumn: string;
      datasetId?: number;
    }
  ];
}>();

const datasets = ref<Dataset[]>([]);
const project = ref<Project | null>(null);
const isLoadingDatasets = ref(false);
const isLoadingProject = ref(false);
const selectedDatasetId = ref<number | undefined>(undefined);
const selectedDataset = ref<Dataset | null>(null);

const showColumnSelection = ref(false);
const excelColumns = ref<string[]>([]);
const selectedFeatureColumns = ref<string[]>([]);
const selectedTargetColumn = ref<string | undefined>(undefined);

const beforeUpload: UploadProps["beforeUpload"] = (file) => {
  if (!validateExcelFile(file)) {
    return false;
  }
  // Clear dataset selection if uploading file
  selectedDatasetId.value = undefined;
  selectedDataset.value = null;
  return false; // Prevent auto upload
};

const fetchDatasets = async () => {
  isLoadingDatasets.value = true;
  try {
    // If projectId is provided, fetch project and filter datasets
    if (props.projectId) {
      const projectResponse = await $fetch(`/api/projects/${props.projectId}`);
      if (projectResponse.success) {
        project.value = projectResponse.project;
        datasets.value = projectResponse.project.datasets || [];
      }
    } else {
      // No project context, show all datasets
      const response = await DatasetService.fetchAll();
      if (response.success) {
        datasets.value = response.datasets;
      }
    }
  } catch (error) {
    console.error("Failed to fetch datasets:", error);
  } finally {
    isLoadingDatasets.value = false;
  }
};

const filterDatasetOption = (input: string, option: any) => {
  const dataset = datasets.value.find((d) => d.id === option.value);
  if (!dataset) return false;
  return dataset.name.toLowerCase().includes(input.toLowerCase());
};

const handleDatasetSelected = (datasetId: number) => {
  selectedDataset.value =
    datasets.value.find((d) => d.id === datasetId) || null;
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

  excelColumns.value = selectedDataset.value.columns;
  showColumnSelection.value = true;
  message.success(
    `Found ${selectedDataset.value.columns.length} columns in the dataset`
  );
};

const handleFileUploaded = async () => {
  if (fileList.value.length === 0) {
    message.error("Please upload a file first");
    return;
  }

  const file = fileList.value[0].originFileObj;
  const columns = await readExcelColumns(file);
  
  if (columns.length > 0) {
    excelColumns.value = columns;
    showColumnSelection.value = true;
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

// Watch for projectId changes
watch(() => props.projectId, () => {
  fetchDatasets();
});
</script>

<style scoped>
.ant-upload-drag-icon {
  margin-bottom: 1rem;
}
</style>
