<template>
  <div class="min-h-screen bg-gray-50 py-8">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <PageHeader />
      
      <div class="mb-8">
        <h1 class="text-4xl font-bold text-gray-900 mb-2">{{ $t('datasets.title') }}</h1>
        <p class="text-lg text-gray-600">{{ $t('datasets.subtitle') }}</p>
      </div>

      <a-card class="mb-6">
        <!-- Upload New Dataset Section -->
        <div class="mb-6">
          <h2 class="text-2xl font-semibold mb-4">{{ $t('datasets.uploadNew') }}</h2>
          
          <a-form layout="vertical">
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item :label="$t('datasets.name')" required>
                  <a-input 
                    v-model:value="newDataset.name" 
                    :placeholder="$t('datasets.namePlaceholder')"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item :label="$t('datasets.description')">
                  <a-input 
                    v-model:value="newDataset.description" 
                    :placeholder="$t('datasets.descriptionPlaceholder')"
                  />
                </a-form-item>
              </a-col>
            </a-row>

            <a-form-item :label="$t('datasets.file')" required>
              <a-upload-dragger
                v-model:file-list="uploadFileList"
                name="file"
                :before-upload="beforeUpload"
                :max-count="1"
                accept=".xlsx,.xls"
              >
                <p class="ant-upload-drag-icon">
                  <i class="i-mdi-cloud-upload text-6xl text-blue-500"></i>
                </p>
                <p class="ant-upload-text">{{ $t('datasets.dragHint') }}</p>
                <p class="ant-upload-hint">{{ $t('datasets.hint') }}</p>
              </a-upload-dragger>
            </a-form-item>

            <a-button
              type="primary"
              size="large"
              :loading="isUploading"
              :disabled="!canUpload"
              @click="handleUploadDataset"
            >
              {{ $t('datasets.uploadButton') }}
            </a-button>
          </a-form>
        </div>

        <a-divider />

        <!-- Datasets List Section -->
        <div>
          <div class="flex justify-between items-center mb-4">
            <h2 class="text-2xl font-semibold">{{ $t('datasets.availableDatasets') }}</h2>
            <a-button @click="fetchDatasets" :loading="isLoadingDatasets">
              <template #icon><i class="i-mdi-refresh"></i></template>
              {{ $t('datasets.refresh') }}
            </a-button>
          </div>

          <a-spin :spinning="isLoadingDatasets">
            <a-empty v-if="datasets.length === 0" :description="$t('datasets.noDatasets')" />
            
            <a-list v-else :data-source="datasets" item-layout="horizontal">
              <template #renderItem="{ item }">
                <a-list-item>
                  <template #actions>
                    <a-button type="link" @click="viewDatasetDetails(item)">
                      {{ $t('datasets.viewDetails') }}
                    </a-button>
                    <a-popconfirm
                      :title="$t('datasets.deleteConfirm')"
                      @confirm="handleDeleteDataset(item.datasetId)"
                    >
                      <a-button type="link" danger>
                        {{ $t('datasets.delete') }}
                      </a-button>
                    </a-popconfirm>
                  </template>
                  
                  <a-list-item-meta>
                    <template #title>
                      <span class="text-lg font-medium">{{ item.name }}</span>
                      <a-tag class="ml-2" color="blue">{{ item.rowCount }} {{ $t('datasets.rows') }}</a-tag>
                    </template>
                    <template #description>
                      <div class="space-y-1">
                        <div v-if="item.description">{{ item.description }}</div>
                        <div class="text-sm text-gray-500">
                          <span>{{ $t('datasets.fileName') }}: {{ item.fileName }}</span>
                          <span class="ml-4">{{ $t('datasets.fileSize') }}: {{ formatFileSize(item.fileSize) }}</span>
                          <span class="ml-4">{{ $t('datasets.columns') }}: {{ item.columns?.length || 0 }}</span>
                        </div>
                        <div class="text-xs text-gray-400">
                          {{ $t('datasets.uploaded') }}: {{ formatDate(item.createdAt) }}
                        </div>
                      </div>
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
          </a-spin>
        </div>
      </a-card>

      <!-- Dataset Details Modal -->
      <a-modal
        v-model:open="detailsModalVisible"
        :title="selectedDataset?.name"
        :footer="null"
        width="800px"
      >
        <div v-if="selectedDataset" class="space-y-4">
          <a-descriptions bordered :column="2">
            <a-descriptions-item :label="$t('datasets.datasetId')">
              {{ selectedDataset.datasetId }}
            </a-descriptions-item>
            <a-descriptions-item :label="$t('datasets.fileName')">
              {{ selectedDataset.fileName }}
            </a-descriptions-item>
            <a-descriptions-item :label="$t('datasets.fileSize')">
              {{ formatFileSize(selectedDataset.fileSize) }}
            </a-descriptions-item>
            <a-descriptions-item :label="$t('datasets.rowCount')">
              {{ selectedDataset.rowCount }}
            </a-descriptions-item>
            <a-descriptions-item :label="$t('datasets.uploaded')" :span="2">
              {{ formatDate(selectedDataset.createdAt) }}
            </a-descriptions-item>
            <a-descriptions-item v-if="selectedDataset.description" :label="$t('datasets.description')" :span="2">
              {{ selectedDataset.description }}
            </a-descriptions-item>
          </a-descriptions>

          <div>
            <h3 class="font-semibold mb-2">{{ $t('datasets.columnsTitle') }}</h3>
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
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { message } from 'ant-design-vue';
import { useI18n } from 'vue-i18n';
import type { UploadProps } from 'ant-design-vue';

const { t } = useI18n();

interface Dataset {
  id: number;
  datasetId: string;
  name: string;
  description?: string;
  filePath: string;
  fileName: string;
  fileSize: number;
  columns: string[];
  rowCount: number;
  createdAt: string;
  updatedAt: string;
}

const datasets = ref<Dataset[]>([]);
const isLoadingDatasets = ref(false);
const isUploading = ref(false);
const uploadFileList = ref([]);
const detailsModalVisible = ref(false);
const selectedDataset = ref<Dataset | null>(null);

const newDataset = ref({
  name: '',
  description: '',
});

const canUpload = computed(() => {
  return newDataset.value.name.trim() && uploadFileList.value.length > 0;
});

const beforeUpload: UploadProps['beforeUpload'] = (file) => {
  const isExcel = file.name.endsWith('.xlsx') || file.name.endsWith('.xls');
  if (!isExcel) {
    message.error(t('datasets.invalidFileType'));
  }
  return false; // Prevent auto upload
};

const fetchDatasets = async () => {
  isLoadingDatasets.value = true;
  try {
    const response = await $fetch('/api/data');
    if (response.success) {
      datasets.value = response.datasets;
    }
  } catch (error) {
    console.error('Failed to fetch datasets:', error);
    message.error(t('datasets.fetchError'));
  } finally {
    isLoadingDatasets.value = false;
  }
};

const handleUploadDataset = async () => {
  if (!canUpload.value) {
    return;
  }

  isUploading.value = true;
  try {
    const formData = new FormData();
    formData.append('file', uploadFileList.value[0].originFileObj);
    formData.append('name', newDataset.value.name);
    if (newDataset.value.description) {
      formData.append('description', newDataset.value.description);
    }

    const response = await $fetch('/api/data', {
      method: 'POST',
      body: formData,
    });

    if (response.success) {
      message.success(t('datasets.uploadSuccess'));
      
      // Reset form
      newDataset.value.name = '';
      newDataset.value.description = '';
      uploadFileList.value = [];
      
      // Refresh datasets list
      await fetchDatasets();
    }
  } catch (error) {
    console.error('Failed to upload dataset:', error);
    message.error(t('datasets.uploadError'));
  } finally {
    isUploading.value = false;
  }
};

const handleDeleteDataset = async (datasetId: string) => {
  try {
    const response = await $fetch(`/api/data/${datasetId}`, {
      method: 'DELETE',
    });

    if (response.success) {
      message.success(t('datasets.deleteSuccess'));
      await fetchDatasets();
    }
  } catch (error) {
    console.error('Failed to delete dataset:', error);
    message.error(t('datasets.deleteError'));
  }
};

const viewDatasetDetails = (dataset: Dataset) => {
  selectedDataset.value = dataset;
  detailsModalVisible.value = true;
};

const formatFileSize = (bytes: number): string => {
  if (!bytes) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
};

const formatDate = (dateString: string): string => {
  if (!dateString) return '';
  const date = new Date(dateString);
  return date.toLocaleString();
};

onMounted(() => {
  fetchDatasets();
});
</script>
