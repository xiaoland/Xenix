<template>
  <default-layout>
    <div class="max-w-7xl mx-auto px-4 py-8">
      <div class="mb-6">
        <h1 class="text-3xl font-bold mb-2">{{ $t("tasks.title") }}</h1>
        <p class="text-gray-600">{{ $t("tasks.subtitle") }}</p>
      </div>

      <a-card class="mb-6">
        <div class="flex gap-4 items-end flex-wrap">
          <div class="flex-1 min-w-[200px]">
            <label class="block text-sm font-medium text-gray-700 mb-2">{{
              $t("tasks.status")
            }}</label>
            <a-select
              v-model:value="statusFilter"
              style="width: 100%"
              @change="fetchTasks"
            >
              <a-select-option value="">{{ $t("tasks.all") }}</a-select-option>
              <a-select-option value="pending">{{
                $t("tasks.pending")
              }}</a-select-option>
              <a-select-option value="running">{{
                $t("tasks.running")
              }}</a-select-option>
              <a-select-option value="completed">{{
                $t("tasks.completed")
              }}</a-select-option>
              <a-select-option value="failed">{{
                $t("tasks.failed")
              }}</a-select-option>
            </a-select>
          </div>

          <div class="flex-1 min-w-[200px]">
            <label class="block text-sm font-medium text-gray-700 mb-2">{{
              $t("tasks.type")
            }}</label>
            <a-select
              v-model:value="typeFilter"
              style="width: 100%"
              @change="fetchTasks"
            >
              <a-select-option value="">{{ $t("tasks.all") }}</a-select-option>
              <a-select-option value="auto-tune">{{
                $t("tasks.autoTune")
              }}</a-select-option>
              <a-select-option value="manual-tune">{{
                $t("tasks.manualTune")
              }}</a-select-option>
              <a-select-option value="predict-file">{{
                $t("tasks.predictFile")
              }}</a-select-option>
              <a-select-option value="predict-inline">{{
                $t("tasks.predictInline")
              }}</a-select-option>
            </a-select>
          </div>

          <a-button
            :loading="loading"
            class="inline-flex items-center"
            @click="fetchTasks"
          >
            <span class="i-mdi-refresh mr-1"></span>
            {{ $t("common.refresh") }}
          </a-button>
        </div>
      </a-card>

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
              <a-tag :color="getStatusColor(record.status)">{{
                record.status
              }}</a-tag>
            </template>

            <template v-else-if="column.key === 'model'">
              <span v-if="record.parameter?.model" class="font-medium">{{
                formatModelName(record.parameter.model)
              }}</span>
              <span v-else class="text-gray-400">-</span>
            </template>

            <template v-else-if="column.key === 'workItem'">
              <router-link
                v-if="record.workItemId"
                :to="`/work-items/${record.workItemId}`"
                class="text-blue-600 hover:text-blue-800"
                >Work Item #{{ record.workItemId }}</router-link
              >
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
                {{ $t("logs.title") }}
              </a-button>
            </template>
          </template>
        </a-table>
      </a-card>

      <a-modal
        v-model:open="logsModalVisible"
        :title="$t('logs.title')"
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
import { message } from "ant-design-vue";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";

import DefaultLayout from "@/features/common/components/DefaultLayout.vue";
import { useFormatters } from "@/hooks";
import { useTasks } from "@/features/tasks/queries";
import { useModels } from "@/features/ml/queries";

const { t } = useI18n();
const { formatDate } = useFormatters();

const { data: tasksData, isLoading: loading, refetch } = useTasks();
const tasks = computed(() => tasksData.value || []);

const logs = ref<any[]>([]);
const loadingLogs = ref(false);
const logsModalVisible = ref(false);
const statusFilter = ref("");
const typeFilter = ref("");
const currentPage = ref(1);

const fetchTasks = refetch;

const columns = [
  { title: t("tasks.id"), key: "id", width: 80 },
  { title: t("tasks.type"), key: "type", width: 140 },
  { title: t("tasks.status"), key: "status", width: 120 },
  { title: t("tasks.model"), key: "model", width: 150 },
  { title: t("tasks.workItem"), key: "workItem", width: 150 },
  { title: t("tasks.created"), key: "createdAt", width: 180 },
  { title: t("tasks.actions"), key: "action", width: 100 },
];

const viewLogs = async (_taskId: number) => {
  logsModalVisible.value = true;
  loadingLogs.value = true;
  try {
    message.info("Logs feature requires backend implementation");
    logs.value = [];
  } catch (err: any) {
    console.error("Failed to fetch logs:", err);
    message.error(err.message || "Failed to fetch logs");
    logs.value = [];
  } finally {
    loadingLogs.value = false;
  }
};

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

const { data: availableModels } = useModels();

const formatModelName = (modelValue: string) => {
  const model = availableModels.value?.find((m) => m.value === modelValue);
  return model ? model.label : modelValue;
};

const formatLogTime = (timestamp: string) => {
  return new Date(timestamp).toLocaleTimeString();
};
</script>
