<template>
  <div
    v-if="Object.keys(tuningTasks).length > 0 || comparisonTaskId"
    class="mt-6"
  >
    <h3 class="text-lg font-medium mb-3">{{ t("logs.title") }}</h3>
    <a-tabs v-model:activeKey="activeTab">
      <a-tab-pane
        v-for="(taskId, modelName) in tuningTasks"
        :key="taskId"
        :tab="modelName"
      >
        <LogPanel :logs="taskLogs[taskId] || []" />
      </a-tab-pane>
      <a-tab-pane
        v-if="comparisonTaskId"
        key="comparison"
        :tab="t('logs.comparison')"
      >
        <LogPanel :logs="taskLogs[comparisonTaskId] || []" />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
const { t } = useI18n();

const props = defineProps<{
  tuningTasks: Record<string, string>;
  comparisonTaskId: string | null;
  taskLogs: Record<string, any[]>;
}>();

const activeTab = defineModel<string>({ required: true });
</script>
