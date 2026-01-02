<template>
  <div class="space-y-4">
    <div class="flex justify-between items-center">
      <h2 class="text-2xl font-semibold">{{ t("prediction.history") }}</h2>
      <a-button type="primary" @click="fetchTasks" :loading="isLoading">
        {{ t("common.refresh") }}
      </a-button>
    </div>

    <a-spin :spinning="isLoading">
      <a-table
        :columns="columns"
        :data-source="tasks"
        :pagination="pagination"
        row-key="id"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'createdAt'">
            {{ formatDate(record.createdAt) }}
          </template>
          <template v-if="column.key === 'model'">
            {{ t(`models.${record.parameter?.model?.replace(".", "_")}`) }}
          </template>
          <template v-if="column.key === 'status'">
            <a-tag :color="getStatusColor(record.status)">
              {{ t(`status.${record.status}`) }}
            </a-tag>
          </template>
        </template>
      </a-table>

      <a-empty
        v-if="!isLoading && tasks.length === 0"
        :description="t('prediction.noPredictions')"
      />
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { TaskService } from "~/services";
import type { TaskInfo } from "~/types";

const { t } = useI18n();

const props = defineProps<{
  workItemId: number;
}>();

const tasks = ref<TaskInfo[]>([]);
const isLoading = ref(false);
const pagination = ref({ pageSize: 10 });
const columns = computed(() => [
  {
    title: t("prediction.createdAt"),
    key: "createdAt",
    dataIndex: "createdAt",
  },
  { title: t("prediction.model"), key: "model", dataIndex: "parameter.model" },
  { title: t("prediction.status"), key: "status", dataIndex: "status" },
]);

// Methods
const fetchTasks = async () => {
  isLoading.value = true;
  try {
    const response = await TaskService.fetchByWorkItemId(props.workItemId, [
      "predict",
    ]);
    if (response.success) {
      tasks.value = response.tasks.sort(
        (a, b) =>
          new Date(b.createdAt || 0).getTime() -
          new Date(a.createdAt || 0).getTime()
      );
    }
  } catch (error) {
    console.error("Failed to fetch prediction tasks:", error);
  } finally {
    isLoading.value = false;
  }
};

const getStatusColor = (status: string) => {
  switch (status) {
    case "completed":
      return "green";
    case "failed":
      return "red";
    case "running":
      return "blue";
    case "pending":
      return "orange";
    default:
      return "default";
  }
};

const formatDate = (dateString: string | undefined) => {
  if (!dateString) return "";
  return new Date(dateString).toLocaleString();
};

// Lifecycle
onMounted(async () => {
  await fetchTasks();
});
</script>
