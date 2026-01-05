<template>
  <div>
    <div v-if="loading" class="text-center py-8">
      <a-spin />
      <p class="mt-2 text-gray-600">Loading datasets...</p>
    </div>

    <div v-else-if="datasets.length === 0" class="text-center py-8">
      <a-empty description="No datasets found">
        <template #image>
          <span class="i-mdi-database-off text-6xl text-gray-400"></span>
        </template>
        <p class="text-gray-600 mb-4">
          Upload a dataset to get started.
        </p>
      </a-empty>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="dataset in datasets"
        :key="dataset.id"
        class="border rounded-lg p-4 hover:border-blue-500 cursor-pointer transition-colors"
        :class="{ 'border-blue-500 bg-blue-50': selectedId === dataset.id }"
        @click="handleSelect(dataset)"
      >
        <div class="flex items-start justify-between mb-2">
          <h4 class="font-medium text-lg">{{ dataset.name }}</h4>
          <span
            v-if="selectedId === dataset.id"
            class="i-mdi-check-circle text-blue-500 text-xl"
          ></span>
        </div>
        <p class="text-sm text-gray-600 mb-2" v-if="dataset.filePath">
          {{ dataset.filePath.split('/').pop() }}
        </p>
        <div class="text-sm text-gray-500">
          <p>{{ dataset.columns.length }} columns</p>
          <p v-if="dataset.createdAt">
            Uploaded: {{ new Date(dataset.createdAt).toLocaleDateString() }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { message } from 'ant-design-vue';
import { DatasetService } from '../../services';

interface Dataset {
  id: number;
  name: string;
  filePath?: string;
  columns: string[];
  createdAt?: string;
}

const props = defineProps<{
  projectId: number;
}>();

const emit = defineEmits<{
  select: [dataset: Dataset];
}>();

const datasets = ref<Dataset[]>([]);
const loading = ref(false);
const selectedId = ref<number | null>(null);

const fetchDatasets = async () => {
  loading.value = true;
  try {
    const response = await DatasetService.listByProject(props.projectId);
    if (response.success && response.datasets) {
      datasets.value = response.datasets;
    }
  } catch (err) {
    console.error('Failed to fetch datasets:', err);
    message.error('Failed to load datasets');
  } finally {
    loading.value = false;
  }
};

const handleSelect = (dataset: Dataset) => {
  selectedId.value = dataset.id;
  emit('select', dataset);
};

onMounted(() => {
  fetchDatasets();
});
</script>
