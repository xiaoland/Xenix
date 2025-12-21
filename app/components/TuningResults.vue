<template>
  <div v-if="hasResults" class="mt-6">
    <h3 class="text-lg font-semibold mb-4">
      {{ t("training.tuningResults") }}
    </h3>
    <a-table
      :dataSource="results"
      :columns="columns"
      :row-key="(record) => record.model"
      :row-selection="rowSelection"
      :pagination="false"
      class="results-table"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'model'">
          <span class="font-medium">{{ formatModelName(record.model) }}</span>
        </template>
        <template v-else-if="column.key === 'r2_test'">
          <span class="text-green-600 font-semibold">{{
            formatMetric(record.r2_test)
          }}</span>
        </template>
        <template v-else-if="['mse_test', 'mae_test'].includes(column.key)">
          <span>{{ formatMetric(record[column.key]) }}</span>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="getStatusColor(record.status)">
            {{
              record.status
                ? t(`status.${record.status.toLowerCase()}`)
                : t("status.pending")
            }}
          </a-tag>
        </template>
      </template>
    </a-table>
    <p class="text-sm text-gray-500 mt-2">
      {{ t("training.selectModelInstruction") }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

const { t } = useI18n();

const props = defineProps<{
  results: any[];
  selectedModel?: string | null;
}>();

const emit = defineEmits<{
  "update:selectedModel": [value: string];
}>();

const hasResults = computed(() => props.results && props.results.length > 0);

const columns = computed(() => [
  { title: t("training.modelColumn"), key: "model", dataIndex: "model" },
  {
    title: t("training.r2Test"),
    key: "r2_test",
    dataIndex: "r2_test",
    sorter: (a: any, b: any) =>
      parseFloat(b.r2_test || 0) - parseFloat(a.r2_test || 0),
  },
  {
    title: t("training.mseTest"),
    key: "mse_test",
    dataIndex: "mse_test",
    sorter: (a: any, b: any) =>
      parseFloat(a.mse_test || 999) - parseFloat(b.mse_test || 999),
  },
  {
    title: t("training.maeTest"),
    key: "mae_test",
    dataIndex: "mae_test",
    sorter: (a: any, b: any) =>
      parseFloat(a.mae_test || 999) - parseFloat(b.mae_test || 999),
  },
  { title: t("training.statusColumn"), key: "status", dataIndex: "status" },
]);

const rowSelection = computed(() => ({
  type: "radio",
  selectedRowKeys: props.selectedModel ? [props.selectedModel] : [],
  onChange: (selectedRowKeys: string[]) => {
    if (selectedRowKeys.length > 0) {
      emit("update:selectedModel", selectedRowKeys[0]);
    }
  },
}));

const formatModelName = (name: string) => {
  return name.replace(/_/g, " ");
};

const formatMetric = (value: string | number) => {
  if (!value) return t("common.na");
  const num = typeof value === "string" ? parseFloat(value) : value;
  return num.toFixed(4);
};

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    completed: "green",
    running: "blue",
    pending: "orange",
    failed: "red",
  };
  return colors[status?.toLowerCase()] || "default";
};
</script>

<style scoped>
.results-table :deep(.ant-table-row) {
  cursor: pointer;
}

.results-table :deep(.ant-table-row:hover) {
  background-color: #f5f5f5;
}

.results-table :deep(.ant-table-row-selected) {
  background-color: #e6f7ff;
}
</style>
