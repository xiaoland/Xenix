<template>
  <a-modal
    :open="open"
    :title="$t('ml.tuning.paramsModalTitle')"
    width="600px"
    :footer="null"
    @update:open="emit('update:open', $event)"
  >
    <div v-if="task" class="params-display">
      <div class="mb-4">
        <h4 class="text-sm font-medium mb-2">
          {{ $t("ml.tuning.model") }}:
          {{ formatModelName(task.parameter?.model) }}
        </h4>
        <a-tag :color="getStatusColor(task.status)">
          {{ task.status }}
        </a-tag>
        <a-tag v-if="task.type === 'auto-tune'" color="blue" class="ml-2">
          {{ $t("ml.tuning.type.auto") }}
        </a-tag>
        <a-tag
          v-else-if="task.type === 'manual-tune'"
          color="green"
          class="ml-2"
        >
          {{ $t("ml.tuning.type.manual") }}
        </a-tag>
      </div>

      <!-- Parameters -->
      <div class="bg-gray-50 rounded p-4 mb-4">
        <h4 class="text-sm font-semibold mb-3">
          {{ $t("ml.tuning.parameters") }}
        </h4>
        <div
          v-for="(value, key) in task.result?.params"
          :key="key"
          class="param-row py-2 border-b border-gray-200 last:border-0"
        >
          <span class="param-key text-gray-600 font-medium">{{ key }}:</span>
          <span class="param-value ml-2 font-mono text-sm">{{
            formatParamValue(value)
          }}</span>
        </div>
      </div>

      <!-- Metrics -->
      <div v-if="task.result?.metrics" class="bg-blue-50 rounded p-4">
        <h4 class="text-sm font-semibold mb-3">
          {{ $t("ml.tuning.metrics") }}
        </h4>
        <div
          v-for="(value, key) in task.result.metrics"
          :key="key"
          class="metric-row py-2 border-b border-blue-100 last:border-0"
        >
          <span class="metric-key text-gray-600 font-medium">{{
            formatMetricKey(key)
          }}</span
          >:
          <span class="metric-value ml-2 font-mono text-sm font-medium">{{
            formatMetric(value)
          }}</span>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import type { Task } from "@xenix/shared";

import { useTaskFormatting } from "@/composables";

interface Props {
  open: boolean;
  task: Task | null;
}

defineProps<Props>();

const emit = defineEmits<{
  "update:open": [value: boolean];
}>();

const {
  formatModelName,
  formatMetricKey,
  formatMetric,
  formatParamValue,
  getStatusColor,
} = useTaskFormatting();
</script>
