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
import { onMounted, watch } from "vue";
import { message } from "ant-design-vue";
import { useUploadStep } from "../composables/useUploadStep";

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

// Use upload step composable
const {
  datasets,
  isLoadingDatasets,
  selectedDatasetId,
  fileList,
  showColumnSelection,
  excelColumns,
  selectedFeatureColumns,
  selectedTargetColumn,
  isLoadingColumns,
  fetchDatasets,
  filterDatasetOption,
  handleDatasetSelected,
  beforeUpload,
  handleContinue,
  handleBackToUpload,
} = useUploadStep(props.projectId);

// Handle column selection confirmation
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
