<template>
  <div class="space-y-6">
    <!-- Step 1: Dataset Selection -->
    <div v-if="currentSubStep === 'dataset'">
      <a-alert
        :message="$t('datasets.selectDataset')"
        :description="$t('datasets.selectDatasetDescription')"
        type="info"
        show-icon
        class="mb-4"
      />
      <DatasetSelector
        :project-id="workItem?.projectId"
        @dataset-selected="handleDatasetSelected"
      />
      <div class="mt-4">
        <NuxtLink
          :to="`/project/${workItem?.projectId}/datasets`"
          class="inline-block"
        >
          <a-button type="default" class="inline-flex items-center gap-2">
            <span class="i-mdi-cloud-upload"></span>
            {{ $t("datasets.uploadNew") }}
          </a-button>
        </NuxtLink>
      </div>
    </div>

    <!-- Step 2: Column Selection -->
    <div v-else-if="currentSubStep === 'columns'">
      <ColumnSelector
        :columns="selectedColumns"
        :feature-columns="featureColumns"
        :target-column="targetColumn"
        @back="goBackToDatasetSelection"
        @confirm="handleColumnsConfirm"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";
import DatasetSelector from "~/components/dataset/DatasetSelector.vue";
import ColumnSelector from "~/components/ml/prepare/ColumnSelector.vue";
import { WorkItemService } from "~/services/workItemService";
import { DatasetService } from "~/services/datasetService";
import type { WorkItem } from "~/types";

const { t } = useI18n();

const props = defineProps<{
  workItemId: number;
}>();

const emit = defineEmits<{
  confirm: [];
}>();

const workItem = ref<WorkItem | null>(null);

// Sub-step state
type SubStep = "dataset" | "columns";
const currentSubStep = ref<SubStep>("dataset");

// Dataset selection state
const selectedDatasetId = ref<number | undefined>(undefined);

// Column selection state
const selectedColumns = ref<string[]>([]);
const featureColumns = ref<string[]>([]);
const targetColumn = ref<string | undefined>(undefined);

/**
 * Fetch work item and initialize state
 */
const fetchWorkItem = async () => {
  try {
    const response = await WorkItemService.fetchById(props.workItemId);
    if (response.success) {
      workItem.value = response.workItem;

      // If work item has saved prepare data, initialize the state
      if (
        workItem.value.datasetId &&
        workItem.value.featureColumns &&
        workItem.value.targetColumn
      ) {
        // Fetch the dataset to get columns
        const datasetResponse = await DatasetService.fetchById(
          workItem.value.datasetId
        );
        if (datasetResponse.success) {
          selectedDatasetId.value = workItem.value.datasetId;
          selectedColumns.value = datasetResponse.dataset.columns;
          featureColumns.value = workItem.value.featureColumns;
          targetColumn.value = workItem.value.targetColumn;
          currentSubStep.value = "columns";
        }
      }
    }
  } catch (error) {
    console.error("Failed to fetch work item:", error);
    message.error(t("workItems.fetchError"));
  }
};

onMounted(() => {
  fetchWorkItem();
});
const handleDatasetSelected = (data: {
  datasetId: number;
  columns: string[];
}) => {
  selectedDatasetId.value = data.datasetId;
  selectedColumns.value = data.columns;
  featureColumns.value = [];
  targetColumn.value = undefined;
  currentSubStep.value = "columns";
  message.success(t("datasets.datasetSelected"));
};

/**
 * Go back to dataset selection
 */
const goBackToDatasetSelection = () => {
  currentSubStep.value = "dataset";
  selectedDatasetId.value = undefined;
  selectedColumns.value = [];
  featureColumns.value = [];
  targetColumn.value = undefined;
};

/**
 * Handle columns confirmation
 */
const handleColumnsConfirm = async (data: {
  featureColumns: string[];
  targetColumn: string;
}) => {
  featureColumns.value = data.featureColumns;
  targetColumn.value = data.targetColumn;

  if (selectedDatasetId.value && workItem.value) {
    try {
      const response = await WorkItemService.update(workItem.value.id, {
        datasetId: selectedDatasetId.value,
        featureColumns: data.featureColumns,
        targetColumn: data.targetColumn,
      });

      if (response.success) {
        // Update local workItem
        workItem.value = response.workItem;
      }

      emit("confirm");

      message.success(
        `${t("columns.selectedFeatures", {
          count: data.featureColumns.length,
        })} ${t("columns.targetSetTag")}`
      );
    } catch (error) {
      console.error("Failed to save prepare data:", error);
      message.error(t("messages.saveError"));
    }
  }
};
</script>
