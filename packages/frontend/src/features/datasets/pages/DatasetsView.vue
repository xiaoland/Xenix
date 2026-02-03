<template>
  <default-layout>
    <div class="max-w-7xl mx-auto px-4 py-8">
      <a-breadcrumb class="mb-6">
        <a-breadcrumb-item>
          <router-link to="/"> {{ $t('navigation.home') }} </router-link>
        </a-breadcrumb-item>
        <a-breadcrumb-item> {{ $t('datasets.title') }} </a-breadcrumb-item>
      </a-breadcrumb>

      <div class="flex justify-between items-center mb-6">
        <div>
          <h1 class="text-3xl font-bold">{{ $t('datasets.title') }}</h1>
          <p class="text-gray-600 mt-1">{{ $t('datasets.subtitle') }}</p>
        </div>
        <a-button
          type="primary"
          class="inline-flex items-center"
          @click="showUploadModal = true"
        >
          <span class="i-mdi-cloud-upload mr-2"></span>
          {{ $t('datasets.uploadNew') }}
        </a-button>
      </div>

      <div v-if="loading" class="text-center py-12">
        <a-spin size="large" />
      </div>

      <div v-else-if="datasets.length === 0" class="text-center py-12">
        <a-empty description="No datasets yet">
          <template #image>
            <span class="i-mdi-database-off text-8xl text-gray-300"></span>
          </template>
          <p class="text-gray-600 mb-4">
            {{ $t('datasets.noDatasets') }}
          </p>
          <a-button
            type="primary"
            class="inline-flex items-center"
            @click="showUploadModal = true"
          >
            <span class="i-mdi-cloud-upload mr-2"></span>
            {{ $t('datasets.uploadNew') }}
          </a-button>
        </a-empty>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <a-card
          v-for="dataset in datasets"
          :key="dataset.id"
          :title="dataset.name"
          class="hover:shadow-lg transition-shadow"
        >
          <template #extra>
            <a-space>
              <a-button
                type="text"
                size="small"
                @click="handleRemoveDuplicates(dataset)"
                :loading="removingId === dataset.id"
              >
                <span class="i-mdi-content-duplicate"></span>
              </a-button>
              <a-button
                type="text"
                danger
                size="small"
                @click="handleDelete(dataset.id)"
              >
                <span class="i-mdi-delete"></span>
              </a-button>
            </a-space>
          </template>
          <div class="space-y-2">
            <p class="text-sm text-gray-600">
              <strong>Columns:</strong> {{ dataset.columns.length }}
            </p>
            <p v-if="dataset.filePath" class="text-sm text-gray-600">
              <strong>File:</strong> {{ dataset.filePath.split("/").pop() }}
            </p>
            <p v-if="dataset.createdAt" class="text-xs text-gray-500">
              Uploaded: {{ new Date(dataset.createdAt).toLocaleDateString() }}
            </p>
            <a-button type="link" size="small" @click="viewDetails(dataset)">
              View Details
            </a-button>
          </div>
        </a-card>
      </div>

      <a-modal
        v-model:open="showUploadModal"
        title="Upload Dataset"
        :footer="null"
        width="600px"
      >
        <add-dataset
          :project-id="projectId"
          @success="handleUploadSuccess"
          @cancel="showUploadModal = false"
        />
      </a-modal>

      <a-modal
        v-model:open="showDetailsModal"
        :title="selectedDataset?.name"
        :footer="null"
        width="700px"
      >
        <div v-if="selectedDataset" class="space-y-4">
          <div>
            <strong>Columns ({{ selectedDataset.columns.length }}):</strong>
            <div class="mt-2 flex flex-wrap gap-2">
              <a-tag v-for="col in selectedDataset.columns" :key="col">
                {{ col }}
              </a-tag>
            </div>
          </div>
          <div v-if="selectedDataset.filePath">
            <strong>File Path:</strong>
            <p class="text-sm text-gray-600 mt-1">
              {{ selectedDataset.filePath }}
            </p>
          </div>
        </div>
      </a-modal>
    </div>
  </default-layout>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { message, Modal } from "ant-design-vue";

import DefaultLayout from "../../common/components/DefaultLayout.vue";
import AddDataset from "../components/AddDataset.vue";
import { useDatasets, useDeleteDataset, useRemoveDuplicates } from "../queries";

interface Dataset {
  id: number;
  name: string;
  filePath?: string;
  columns: string[];
  createdAt?: string;
}

const route = useRoute();
const router = useRouter();
const projectId = Number(route.params.projectId);

const { data: datasetsData, isLoading: loading, refetch } = useDatasets();
const { mutate: deleteDataset } = useDeleteDataset();
const { mutate: removeDuplicates } = useRemoveDuplicates();

const datasets = computed(() => datasetsData.value || []);

const showUploadModal = ref(false);
const showDetailsModal = ref(false);
const selectedDataset = ref<Dataset | null>(null);
const removingId = ref<number | null>(null);

const handleUploadSuccess = (dataset: Dataset) => {
  showUploadModal.value = false;
  message.success("Dataset uploaded successfully");
  refetch();
  // Navigate to dataset detail page
  router.push(`/projects/${projectId}/datasets/${dataset.id}`);
};

const viewDetails = (dataset: Dataset) => {
  selectedDataset.value = dataset;
  showDetailsModal.value = true;
};

const handleDelete = (id: number) => {
  Modal.confirm({
    title: "Delete Dataset",
    content: "Are you sure you want to delete this dataset? This action cannot be undone.",
    okText: "Delete",
    okType: "danger",
    onOk: () => {
      deleteDataset(id, {
        onSuccess: () => {
          message.success('Dataset deleted successfully');
        },
        onError: (err: any) => {
          console.error('Failed to delete dataset:', err);
          message.error('Failed to delete dataset');
        },
      });
    },
  });
};

const handleRemoveDuplicates = (dataset: Dataset) => {
  Modal.confirm({
    title: "Remove Duplicates",
    content: `This will create a new dataset "${dataset.name} (deduplicated)" with duplicate rows removed. The original dataset will remain unchanged.`,
    okText: "Remove Duplicates",
    onOk: () => {
      removingId.value = dataset.id;
      removeDuplicates(dataset.id, {
        onSuccess: (result: any) => {
          removingId.value = null;
          message.success(`Duplicates removed: ${result.removedCount} rows removed from ${result.originalRowCount} total rows`);
          refetch();
        },
        onError: (err: any) => {
          removingId.value = null;
          console.error('Failed to remove duplicates:', err);
          message.error('Failed to remove duplicates');
        },
      });
    },
  });
};
</script>
