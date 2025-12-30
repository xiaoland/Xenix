<template>
  <div class="space-y-4">
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
          @change="(value: any) => handleDatasetSelected(value)"
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
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch, ref } from "vue";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";
import { DatasetService, ProjectService } from "~/services";
import type { Dataset } from "~/types";

const { t } = useI18n();

const props = defineProps<{
  projectId?: number;
}>();

const emit = defineEmits<{
  datasetSelected: [
    {
      datasetId: number;
      columns: string[];
    }
  ];
}>();

// State
const datasets = ref<Dataset[]>([]);
const isLoadingDatasets = ref(false);
const selectedDatasetId = ref<number | undefined>(undefined);

/**
 * Fetch available datasets
 */
const fetchDatasets = async () => {
  isLoadingDatasets.value = true;
  try {
    if (props.projectId) {
      const projectResponse = await ProjectService.fetchById(props.projectId);
      if (projectResponse.success) {
        datasets.value = projectResponse.project.datasets || [];
      }
    } else {
      const response = await DatasetService.fetchAll();
      if (response.success) {
        datasets.value = response.datasets;
      }
    }
  } catch (error) {
    console.error("Failed to fetch datasets:", error);
    message.error(t("datasets.fetchError"));
  } finally {
    isLoadingDatasets.value = false;
  }
};

/**
 * Filter dataset options in select dropdown
 */
const filterDatasetOption = (input: string, option: any) => {
  const dataset = datasets.value.find((d: Dataset) => d.id === option.value);
  if (!dataset) return false;
  return dataset.name.toLowerCase().includes(input.toLowerCase());
};

/**
 * Handle dataset selection from dropdown
 */
const handleDatasetSelected = (datasetId: number | string | undefined) => {
  if (typeof datasetId !== "number") return;
  selectedDatasetId.value = datasetId;
  const dataset = datasets.value.find((d: Dataset) => d.id === datasetId);

  if (dataset) {
    message.success(t("datasets.datasetSelected"));
    emit("datasetSelected", {
      datasetId: dataset.id,
      columns: dataset.columns || [],
    });
  }
};

onMounted(() => {
  fetchDatasets();
});

// Watch for projectId changes
watch(
  () => props.projectId,
  () => {
    fetchDatasets();
  }
);
</script>

<style scoped>
.ant-upload-drag-icon {
  margin-bottom: 1rem;
}
</style>
