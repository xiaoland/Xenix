<template>
  <div class="min-h-screen bg-gray-50 py-8">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <PageHeader />

      <!-- Breadcrumb -->
      <div class="mb-4">
        <a-breadcrumb>
          <a-breadcrumb-item>
            <NuxtLink to="/">{{ $t("navigation.home") }}</NuxtLink>
          </a-breadcrumb-item>
          <a-breadcrumb-item v-if="project">
            {{ project.name }}
          </a-breadcrumb-item>
          <a-breadcrumb-item>Datasets</a-breadcrumb-item>
        </a-breadcrumb>
      </div>

      <div v-if="isLoading" class="text-center py-8">
        <a-spin size="large" />
      </div>

      <div v-else-if="!project" class="text-center py-8">
        <a-result
          status="404"
          title="Project not found"
          sub-title="The project you are looking for does not exist."
        >
          <template #extra>
            <a-button type="primary" @click="$router.push('/')">
              {{ $t("navigation.home") }}
            </a-button>
          </template>
        </a-result>
      </div>

      <div v-else>
        <div class="text-center mb-8">
          <h1 class="text-4xl font-bold text-gray-900 mb-2">
            Manage Datasets - {{ project.name }}
          </h1>
          <p class="text-lg text-gray-600">
            Upload and manage datasets for this project
          </p>
        </div>

        <a-card class="mb-6">
          <div class="mb-4">
            <h3 class="text-lg font-semibold mb-3">Upload New Dataset</h3>
            <UploadDataset
              :project-id="project.id"
              @dataset-uploaded="handleDatasetUploaded"
              @dataset-selected="handleDatasetSelected"
            />
          </div>
        </a-card>

        <a-card>
          <div class="flex justify-between items-center mb-4">
            <h3 class="text-lg font-semibold">Project Datasets</h3>
            <a-button @click="fetchProjectDatasets">
              <template #icon><span class="i-mdi-refresh" /></template>
              Refresh
            </a-button>
          </div>

          <a-spin :spinning="isLoadingDatasets">
            <a-empty
              v-if="datasets.length === 0"
              description="No datasets in this project yet."
            />

            <a-list v-else :data-source="datasets" item-layout="horizontal">
              <template #renderItem="{ item }">
                <a-list-item>
                  <template #actions>
                    <a-button type="link" @click="viewDatasetDetails(item)">
                      View Details
                    </a-button>
                    <a-popconfirm
                      title="Are you sure you want to delete this dataset?"
                      @confirm="deleteDataset(item.id)"
                    >
                      <a-button type="link" danger> Delete </a-button>
                    </a-popconfirm>
                  </template>

                  <a-list-item-meta>
                    <template #title>
                      <span class="text-lg font-medium">{{ item.name }}</span>
                    </template>
                    <template #description>
                      <div class="space-y-1">
                        <div v-if="item.description">
                          {{ item.description }}
                        </div>
                        <div class="text-sm text-gray-500">
                          <span>File: {{ item.fileName }}</span>
                          <span class="ml-4">{{ item.rowCount }} rows</span>
                          <span class="ml-4"
                            >{{ item.columns?.length || 0 }} columns</span
                          >
                        </div>
                        <div class="text-xs text-gray-400">
                          Uploaded: {{ formatDate(item.createdAt) }}
                        </div>
                      </div>
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
          </a-spin>
        </a-card>

        <!-- Dataset Details Modal -->
        <a-modal
          v-model:open="showDatasetDetailsModal"
          :title="selectedDataset?.name"
          :footer="null"
          width="800px"
        >
          <div v-if="selectedDataset" class="space-y-4">
            <a-descriptions bordered :column="2">
              <a-descriptions-item label="Dataset ID">
                {{ selectedDataset.id }}
              </a-descriptions-item>
              <a-descriptions-item label="File Name">
                {{ selectedDataset.fileName }}
              </a-descriptions-item>
              <a-descriptions-item label="Row Count">
                {{ selectedDataset.rowCount }}
              </a-descriptions-item>
              <a-descriptions-item label="Created">
                {{ formatDate(selectedDataset.createdAt) }}
              </a-descriptions-item>
              <a-descriptions-item
                v-if="selectedDataset.description"
                label="Description"
                :span="2"
              >
                {{ selectedDataset.description }}
              </a-descriptions-item>
            </a-descriptions>

            <div>
              <h4 class="font-semibold mb-2">
                Columns ({{ selectedDataset.columns?.length || 0 }})
              </h4>
              <div class="flex flex-wrap gap-2">
                <a-tag
                  v-for="col in selectedDataset.columns"
                  :key="col"
                  color="blue"
                >
                  {{ col }}
                </a-tag>
              </div>
            </div>
          </div>
        </a-modal>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";
import UploadDataset from "~/components/dataset/UploadDataset.vue";
import PageHeader from "~/components/common/PageHeader.vue";
import type { Project, Dataset } from "../../../types";

const { t } = useI18n();
const route = useRoute();

const project = ref<Project | null>(null);
const datasets = ref<Dataset[]>([]);
const isLoading = ref(false);
const isLoadingDatasets = ref(false);

const showDatasetDetailsModal = ref(false);
const selectedDataset = ref<Dataset | null>(null);

const fetchProject = async () => {
  const projectId = Number(route.params.id);
  if (isNaN(projectId)) return;

  isLoading.value = true;
  try {
    const response = await $fetch(`/api/projects/${projectId}`);
    if (response.success) {
      project.value = response.project as any;
      datasets.value = (response.project.datasets || []) as any;
    }
  } catch (error) {
    console.error("Failed to fetch project:", error);
    message.error(t("projects.fetchError"));
  } finally {
    isLoading.value = false;
  }
};

const fetchProjectDatasets = async () => {
  const projectId = Number(route.params.id);
  if (isNaN(projectId)) return;

  isLoadingDatasets.value = true;
  try {
    const response = await $fetch(`/api/projects/${projectId}`);
    if (response.success) {
      datasets.value = (response.project.datasets || []) as any;
    }
  } catch (error) {
    console.error("Failed to fetch datasets:", error);
    message.error(t("datasets.fetchError"));
  } finally {
    isLoadingDatasets.value = false;
  }
};

/**
 * Handle dataset upload from UploadDataset component
 */
const handleDatasetUploaded = async () => {
  message.success(t("datasets.uploadSuccess"));
  await fetchProjectDatasets();
};

/**
 * Handle dataset selection from UploadDataset component
 */
const handleDatasetSelected = async () => {
  message.success(t("datasets.datasetSelected"));
  await fetchProjectDatasets();
};

const deleteDataset = async (id: number) => {
  try {
    const response = await $fetch(`/api/data/${id}`, {
      method: "DELETE",
    });

    if (response.success) {
      message.success(t("datasets.deleteSuccess"));
      await fetchProjectDatasets();
    }
  } catch (error) {
    console.error("Failed to delete dataset:", error);
    message.error(t("datasets.deleteError"));
  }
};

const viewDatasetDetails = (dataset: Dataset) => {
  selectedDataset.value = dataset;
  showDatasetDetailsModal.value = true;
};

const formatDate = (dateString: string): string => {
  if (!dateString) return "";
  const date = new Date(dateString);
  return date.toLocaleString();
};

onMounted(() => {
  fetchProject();
});
</script>

<style scoped>
.ant-upload-drag-icon {
  margin-bottom: 1rem;
}
</style>
