<template>
  <default-layout>
    <div class="max-w-7xl mx-auto px-4 py-8">
      <!-- Breadcrumb -->
      <a-breadcrumb class="mb-6">
        <a-breadcrumb-item>
          <router-link to="/">Home</router-link>
        </a-breadcrumb-item>
        <a-breadcrumb-item> Datasets </a-breadcrumb-item>
      </a-breadcrumb>

      <!-- Header -->
      <div class="flex justify-between items-center mb-6">
        <div>
          <h1 class="text-3xl font-bold">Datasets</h1>
          <p class="text-gray-600 mt-1">Manage datasets for your project</p>
        </div>
        <a-button
          type="primary"
          class="inline-flex items-center"
          @click="showUploadModal = true"
        >
          <span class="i-mdi-cloud-upload mr-2"></span>
          Upload Dataset
        </a-button>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="text-center py-12">
        <a-spin size="large" />
      </div>

      <!-- Empty State -->
      <div v-else-if="datasets.length === 0" class="text-center py-12">
        <a-empty description="No datasets yet">
          <template #image>
            <span class="i-mdi-database-off text-8xl text-gray-300"></span>
          </template>
          <p class="text-gray-600 mb-4">
            Upload a dataset to get started with machine learning.
          </p>
          <a-button
            type="primary"
            class="inline-flex items-center"
            @click="showUploadModal = true"
          >
            <span class="i-mdi-cloud-upload mr-2"></span>
            Upload First Dataset
          </a-button>
        </a-empty>
      </div>

      <!-- Dataset List -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <a-card
          v-for="dataset in datasets"
          :key="dataset.id"
          :title="dataset.name"
          class="hover:shadow-lg transition-shadow"
        >
          <template #extra>
            <a-button
              type="text"
              danger
              size="small"
              @click="handleDelete(dataset.id)"
            >
              <span class="i-mdi-delete"></span>
            </a-button>
          </template>
          <div class="space-y-2">
            <p class="text-sm text-gray-600">
              <strong>Columns:</strong> {{ dataset.columns.length }}
            </p>
            <p class="text-sm text-gray-600" v-if="dataset.filePath">
              <strong>File:</strong> {{ dataset.filePath.split("/").pop() }}
            </p>
            <p class="text-xs text-gray-500" v-if="dataset.createdAt">
              Uploaded: {{ new Date(dataset.createdAt).toLocaleDateString() }}
            </p>
            <a-button type="link" size="small" @click="viewDetails(dataset)">
              View Details
            </a-button>
          </div>
        </a-card>
      </div>

      <!-- Upload Modal -->
      <a-modal
        v-model:open="showUploadModal"
        title="Upload Dataset"
        :footer="null"
        width="600px"
      >
        <dataset-upload
          :project-id="projectId"
          @success="handleUploadSuccess"
          @cancel="showUploadModal = false"
        />
      </a-modal>

      <!-- Details Modal -->
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
import { useRoute } from "vue-router";
import { message, Modal } from "ant-design-vue";
import DefaultLayout from "../../layouts/DefaultLayout.vue";
import DatasetUpload from "../../components/dataset/DatasetUpload.vue";
import { useDatasets, useDeleteDataset } from "../../composables";

interface Dataset {
  id: number;
  name: string;
  filePath?: string;
  columns: string[];
  createdAt?: string;
}

const route = useRoute();
const projectId = Number(route.params.projectId);

// Use composables for data fetching
const { data: datasetsData, isLoading: loading, refetch } = useDatasets();
const { mutate: deleteDataset } = useDeleteDataset();

const datasets = computed(() => datasetsData.value || []);

const showUploadModal = ref(false);
const showDetailsModal = ref(false);
const selectedDataset = ref<Dataset | null>(null);

const handleUploadSuccess = () => {
  showUploadModal.value = false;
  message.success("Dataset uploaded successfully");
  refetch();
};

const viewDetails = (dataset: Dataset) => {
  selectedDataset.value = dataset;
  showDetailsModal.value = true;
};

const handleDelete = (id: number) => {
  Modal.confirm({
    title: "Delete Dataset",
    content:
      "Are you sure you want to delete this dataset? This action cannot be undone.",
    okText: "Delete",
    okType: "danger",
    onOk: () => {
      deleteDataset(id, {
        onSuccess: () => {
          message.success("Dataset deleted successfully");
        },
        onError: (error: any) => {
          console.error("Failed to delete dataset:", error);
          message.error("Failed to delete dataset");
        },
      });
    },
  });
};
</script>
