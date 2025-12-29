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
            
            <a-form layout="vertical">
              <a-form-item label="Dataset Name" required>
                <a-input
                  v-model:value="newDataset.name"
                  placeholder="Enter dataset name"
                />
              </a-form-item>
              
              <a-form-item label="Description">
                <a-textarea
                  v-model:value="newDataset.description"
                  placeholder="Optional description"
                  :rows="2"
                />
              </a-form-item>
              
              <a-form-item label="Data File" required>
                <a-upload-dragger
                  v-model:file-list="fileList"
                  name="file"
                  :before-upload="beforeUpload"
                  :max-count="1"
                  accept=".xlsx,.xls"
                >
                  <p class="ant-upload-drag-icon">
                    <span class="i-mdi-cloud-upload text-6xl text-blue-500 inline-block"></span>
                  </p>
                  <p class="ant-upload-text">Click or drag Excel file to upload</p>
                  <p class="ant-upload-hint">
                    Support for Excel files (.xlsx, .xls)
                  </p>
                </a-upload-dragger>
              </a-form-item>
              
              <a-button
                type="primary"
                :loading="isUploading"
                :disabled="!newDataset.name || fileList.length === 0"
                @click="handleUploadDataset"
              >
                Upload Dataset
              </a-button>
            </a-form>
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
                      <a-button type="link" danger>
                        Delete
                      </a-button>
                    </a-popconfirm>
                  </template>

                  <a-list-item-meta>
                    <template #title>
                      <span class="text-lg font-medium">{{ item.name }}</span>
                    </template>
                    <template #description>
                      <div class="space-y-1">
                        <div v-if="item.description">{{ item.description }}</div>
                        <div class="text-sm text-gray-500">
                          <span>File: {{ item.fileName }}</span>
                          <span class="ml-4">{{ item.rowCount }} rows</span>
                          <span class="ml-4">{{ item.columns?.length || 0 }} columns</span>
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
              <h4 class="font-semibold mb-2">Columns ({{ selectedDataset.columns?.length || 0 }})</h4>
              <div class="flex flex-wrap gap-2">
                <a-tag v-for="col in selectedDataset.columns" :key="col" color="blue">
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
import { useRoute, useRouter } from "vue-router";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";
import type { Project, Dataset } from "../../../types";
import type { UploadProps } from "ant-design-vue";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

const project = ref<Project | null>(null);
const datasets = ref<Dataset[]>([]);
const isLoading = ref(false);
const isLoadingDatasets = ref(false);
const isUploading = ref(false);

const fileList = ref<any[]>([]);
const newDataset = ref({
  name: "",
  description: "",
});

const showDatasetDetailsModal = ref(false);
const selectedDataset = ref<Dataset | null>(null);

const fetchProject = async () => {
  const projectId = Number(route.params.id);
  if (isNaN(projectId)) return;

  isLoading.value = true;
  try {
    const response = await $fetch(`/api/projects/${projectId}`);
    if (response.success) {
      project.value = response.project;
      datasets.value = response.project.datasets || [];
    }
  } catch (error) {
    console.error("Failed to fetch project:", error);
    message.error("Failed to fetch project");
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
      datasets.value = response.project.datasets || [];
    }
  } catch (error) {
    console.error("Failed to fetch datasets:", error);
    message.error("Failed to fetch datasets");
  } finally {
    isLoadingDatasets.value = false;
  }
};

const beforeUpload: UploadProps["beforeUpload"] = (file) => {
  const isExcel =
    file.type === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
    file.type === "application/vnd.ms-excel" ||
    file.name.endsWith(".xlsx") ||
    file.name.endsWith(".xls");

  if (!isExcel) {
    message.error("You can only upload Excel files!");
    return false;
  }
  return false; // Prevent auto upload
};

const handleUploadDataset = async () => {
  if (!newDataset.value.name || fileList.value.length === 0) {
    message.error("Please provide dataset name and file");
    return;
  }

  const formData = new FormData();
  formData.append("file", fileList.value[0].originFileObj);
  formData.append("name", newDataset.value.name);
  if (newDataset.value.description) {
    formData.append("description", newDataset.value.description);
  }
  formData.append("projectId", String(project.value?.id));

  isUploading.value = true;
  try {
    const response = await $fetch("/api/data", {
      method: "POST",
      body: formData,
    });

    if (response.success) {
      message.success("Dataset uploaded successfully");
      newDataset.value = { name: "", description: "" };
      fileList.value = [];
      await fetchProjectDatasets();
    }
  } catch (error) {
    console.error("Failed to upload dataset:", error);
    message.error("Failed to upload dataset");
  } finally {
    isUploading.value = false;
  }
};

const deleteDataset = async (id: number) => {
  try {
    const response = await $fetch(`/api/data/${id}`, {
      method: "DELETE",
    });

    if (response.success) {
      message.success("Dataset deleted successfully");
      await fetchProjectDatasets();
    }
  } catch (error) {
    console.error("Failed to delete dataset:", error);
    message.error("Failed to delete dataset");
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
