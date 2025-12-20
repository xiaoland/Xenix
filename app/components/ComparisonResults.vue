<template>
  <div v-if="comparisonResults" class="mt-6">
    <h3 class="text-lg font-medium mb-3">Model Comparison Results</h3>
    <a-table
      :columns="columns"
      :data-source="comparisonResults.results"
      :pagination="false"
      bordered
      size="small"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'Model'">
          <a-tag v-if="record.Model === comparisonResults.bestModel" color="green">
            {{ record.Model }} ⭐
          </a-tag>
          <span v-else>{{ record.Model }}</span>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  comparisonResults: any;
}>();

const columns = [
  { title: 'Model', dataIndex: 'Model', key: 'Model' },
  { title: 'MSE (Train)', dataIndex: 'MSE_train', key: 'MSE_train' },
  { title: 'MAE (Train)', dataIndex: 'MAE_train', key: 'MAE_train' },
  { title: 'R² (Train)', dataIndex: 'R2_train', key: 'R2_train' },
  { title: 'MSE (Test)', dataIndex: 'MSE_test', key: 'MSE_test' },
  { title: 'MAE (Test)', dataIndex: 'MAE_test', key: 'MAE_test' },
  { title: 'R² (Test)', dataIndex: 'R2_test', key: 'R2_test' },
];
</script>
