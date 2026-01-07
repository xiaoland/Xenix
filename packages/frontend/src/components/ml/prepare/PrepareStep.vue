<template>
  <div class="space-y-6">
    <!-- Info Alert -->
    <a-alert
      message="Prepare Your Data"
      description="Select a dataset and choose the feature columns and target column for your machine learning model."
      type="info"
      show-icon
      class="mb-4"
    ></a-alert>

    <!-- Dataset Selection -->
    <div v-if="!selectedDatasetId">
      <h3 class="text-lg font-semibold mb-4">Step 1: Select Dataset</h3>
      <dataset-selector
        :project-id="workItem.projectId"
        @select="handleDatasetSelect"
      ></dataset-selector>
      <div class="mt-4">
        <router-link :to="'/projects/' + workItem.projectId + '/datasets'">
          <a-button type="default" class="inline-flex items-center">
            <span class="i-mdi-cloud-upload mr-2"></span>
            Upload New Dataset
          </a-button>
        </router-link>
      </div>
    </div>

    <!-- Column Selection -->
    <div v-else>
      <h3 class="text-lg font-semibold mb-4">Step 2: Select Columns</h3>

      <div class="bg-gray-50 p-4 rounded mb-4">
        <div class="flex items-center justify-between">
          <div>
            <span class="font-medium">Selected Dataset:</span>
            <span class="ml-2">{{ selectedDatasetName }}</span>
          </div>
          <a-button size="small" @click="changeDataset">Change</a-button>
        </div>
      </div>

      <column-selector
        :columns="datasetColumns"
        :feature-columns="featureColumns"
        :target-column="targetColumn"
        @update:feature-columns="featureColumns = $event"
        @update:target-column="targetColumn = $event"
      ></column-selector>

      <div class="flex justify-between mt-6">
        <a-button @click="changeDataset"> Back to Dataset Selection </a-button>
        <a-button
          type="primary"
          :disabled="!canConfirm"
          :loading="saving"
          @click="handleConfirm"
        >
          Confirm and Continue
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue';

import { computed, ref } from 'vue';

import { useUpdateWorkItem } from '../../../composables';
import DatasetSelector from '../../dataset/DatasetSelector.vue';
import ColumnSelector from './ColumnSelector.vue';

interface WorkItem {
  id: number;
  projectId: number;
  datasetId?: number;
  featureColumns?: string[];
  targetColumn?: string;
}

interface Dataset {
  id: number;
  name: string;
  columns: string[];
}

const props = defineProps<{
  workItem: WorkItem;
}>();

const emit = defineEmits<{
  confirm: [];
}>();

const selectedDatasetId = ref<number | undefined>(props.workItem.datasetId);
const selectedDatasetName = ref<string>('');
const datasetColumns = ref<string[]>([]);
const featureColumns = ref<string[]>(props.workItem.featureColumns || []);
const targetColumn = ref<string | undefined>(props.workItem.targetColumn);

// Use composable for updating work item
const { mutate: updateWorkItem, isPending: saving } = useUpdateWorkItem();

const canConfirm = computed(() => {
  return (
    selectedDatasetId.value &&
    featureColumns.value.length > 0 &&
    targetColumn.value
  );
});

const handleDatasetSelect = async (dataset: Dataset) => {
  selectedDatasetId.value = dataset.id;
  selectedDatasetName.value = dataset.name;
  datasetColumns.value = dataset.columns;

  // Reset column selections when changing dataset
  featureColumns.value = [];
  targetColumn.value = undefined;
};

const changeDataset = () => {
  selectedDatasetId.value = undefined;
  selectedDatasetName.value = '';
  datasetColumns.value = [];
  featureColumns.value = [];
  targetColumn.value = undefined;
};

const handleConfirm = () => {
  if (!canConfirm.value) return;

  updateWorkItem(
    {
      id: props.workItem.id,
      updates: {
        datasetId: selectedDatasetId.value,
        featureColumns: featureColumns.value,
        targetColumn: targetColumn.value,
      },
    },
    {
      onSuccess: () => {
        message.success('Dataset configuration saved successfully');
        emit('confirm');
      },
      onError: (error: any) => {
        console.error('Failed to save configuration:', error);
        message.error('Failed to save configuration');
      },
    }
  );
};
</script>
