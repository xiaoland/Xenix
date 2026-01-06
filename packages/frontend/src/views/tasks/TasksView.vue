<template>
  <default-layout>
    <div class="max-w-7xl mx-auto px-4 py-8">
      <div class="mb-6">
        <h1 class="text-3xl font-bold mb-2">Task Monitor</h1>
        <p class="text-gray-600">
          Monitor all background tasks across your projects
        </p>
      </div>

      <!-- Filters -->
      <a-card class="mb-6">
        <div class="flex gap-4 items-end flex-wrap">
          <div class="flex-1 min-w-[200px]">
            <label class="block text-sm font-medium text-gray-700 mb-2">Status</label>
            <a-select
              v-model:value="statusFilter"
              style="width: 100%"
              @change="fetchTasks"
            >
              <a-select-option value="">All</a-select-option>
              <a-select-option value="pending">Pending</a-select-option>
              <a-select-option value="running">Running</a-select-option>
              <a-select-option value="completed">Completed</a-select-option>
              <a-select-option value="failed">Failed</a-select-option>
            </a-select>
          </div>

          <div class="flex-1 min-w-[200px]">
            <label class="block text-sm font-medium text-gray-700 mb-2">Type</label>
            <a-select
              v-model:value="typeFilter"
              style="width: 100%"
              @change="fetchTasks"
            >
              <a-select-option value="">All</a-select-option>
              <a-select-option value="auto-tune">Auto-Tune</a-select-option>
              <a-select-option value="manual-tune">Manual-Tune</a-select-option>
              <a-select-option value="predict-file">
Predict (File)
</a-select-option>
              <a-select-option value="predict-inline">
Predict (Inline)
</a-select-option>
            </a-select>
          </div>

          <a-button
            :loading="loading"
            class="inline-flex items-center"
            @click="fetchTasks"
          >
            <span class="i-mdi-refresh mr-1"></span>
            Refresh
          </a-button>
        </div>
      </a-card>

      <!-- Tasks Table -->
      <a-card>
        <a-table
          :columns="columns"
          :data-source="tasks"
          :loading="loading"
          :pagination="{
            current: currentPage,
            pageSize: 20,
            total: tasks.length,
            showSizeChanger: false,
          }"
          row-key="id"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'id'">
              <span class="font-mono text-sm">#{{ record.id }}</span>
            </template>

            <template v-else-if="column.key === 'type'">
              <a-tag>{{ record.type }}</a-tag>
            </template>

            <template v-else-if="column.key === 'status'">
              <a-tag :color="getStatusColor(record.status)">
                {{ record.status }}
              </a-tag>
            </template>

            <template v-else-if="column.key === 'model'">
              <span v-if="record.parameter?.model" class="font-medium">
                {{ formatModelName(record.parameter.model) }}
              </span>
              <span v-else class="text-gray-400">-</span>
            </template>

            <template v-else-if="column.key === 'workItem'">
              <router-link
                v-if="record.workItemId"
                :to="`/work-items/${record.workItemId}`"
                class="text-blue-600 hover:text-blue-800"
              >
                Work Item #{{ record.workItemId }}
              </router-link>
              <span v-else class="text-gray-400">-</span>
            </template>

            <template v-else-if="column.key === 'createdAt'">
              <span class="text-sm">{{ formatDate(record.createdAt) }}</span>
            </template>

            <template v-else-if="column.key === 'action'">
              <a-button
                size="small"
                class="inline-flex items-center"
                @click="viewLogs(record.id)"
              >
                <span class="i-mdi-file-document-outline mr-1"></span>
                Logs
              </a-button>
            </template>
          </template>
        </a-table>
      </a-card>

      <!-- Logs Modal -->
      <a-modal
        v-model:open="logsModalVisible"
        title="Task Logs"
        :footer="null"
        width="800px"
      >
        <div v-if="loadingLogs" class="text-center py-8">
          <a-spin />
        </div>
        <div v-else-if="logs.length > 0" class="space-y-2">
          <div
            v-for="log in logs"
            :key="log.timestamp"
            class="p-2 bg-gray-50 rounded font-mono text-sm"
          >
            <span class="text-gray-500">{{
              formatLogTime(log.timestamp)
            }}</span>
            <span class="ml-2">{{ log.message }}</span>
          </div>
        </div>
        <div v-else class="text-center py-8 text-gray-500">
          No logs available
        </div>
      </a-modal>
    </div>
  </default-layout>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { message } from 'ant-design-vue';
import DefaultLayout from '../../layouts/DefaultLayout.vue';
import { useTasks, useFormatters } from '../../composables';
import { AVAILABLE_MODELS } from '../../constants/models';
const { formatDate } = useFormatters();

// Use composables for data fetching with auto-refetch
const { data: tasksData, isLoading: loading, refetch } = useTasks();

// Computed property to safely access tasks array
const tasks = computed(() => tasksData.value || []);

// State
const logs = ref<any[]>([]);
const loadingLogs = ref(false);
const logsModalVisible = ref(false);
const statusFilter = ref("");
const typeFilter = ref("");
const currentPage = ref(1);

const fetchTasks = refetch;

// Table columns
const columns = [
  { title: "ID", key: "id", width: 80 },
  { title: "Type", key: "type", width: 140 },
  { title: "Status", key: "status", width: 120 },
  { title: "Model", key: "model", width: 150 },
  { title: "Work Item", key: "workItem", width: 150 },
  { title: "Created", key: "createdAt", width: 180 },
  { title: "Action", key: "action", width: 100 },
];

/**
 * View task logs
 * Note: This would need a corresponding composable for fetching logs
 */
const viewLogs = async (_taskId: number) => {
  logsModalVisible.value = true;
  loadingLogs.value = true;

  try {
    // TODO: Create useTaskLogs composable
    // For now, show message that logs feature needs backend endpoint
    message.info('Logs feature requires backend implementation');
    logs.value = [];
  } catch (err: any) {
    console.error('Failed to fetch logs:', err);
    message.error(err.message || 'Failed to fetch logs');
    logs.value = [];
  } finally {
    loadingLogs.value = false;
  }
};

/**
 * Get status color
 */
const getStatusColor = (status: string) => {
  switch (status) {
    case "completed":
      return "success";
    case "failed":
      return "error";
    case "running":
      return "processing";
    case "pending":
      return "default";
    default:
      return "default";
  }
};

/**
 * Format model name
 */
const formatModelName = (modelValue: string) => {
  const model = AVAILABLE_MODELS.find((m) => m.value === modelValue);
  return model ? model.label : modelValue;
};

/**
 * Format log timestamp
 */
const formatLogTime = (timestamp: string) => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString();
};
</script>
