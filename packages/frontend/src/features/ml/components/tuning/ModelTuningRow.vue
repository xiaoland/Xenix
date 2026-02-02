<template>
  <!-- Model Column -->
  <template v-if="column.key === 'model'">
    <span class="font-medium">{{
      formatModelName((task?.parameter as any)?.model)
    }}</span>
  </template>

  <!-- Type Column -->
  <template v-else-if="column.key === 'type'">
    <a-tag
      v-if="task?.type === 'auto-tune'"
      color="blue"
      class="min-w-[60px] text-center"
    >
      {{ $t("ml.tuning.type.auto") }}
    </a-tag>
    <a-tag
      v-else-if="task?.type === 'manual-tune'"
      color="green"
      class="min-w-[60px] text-center"
    >
      {{ $t("ml.tuning.type.manual") }}
    </a-tag>
  </template>

  <!-- Status Column -->
  <template v-else-if="column.key === 'status'">
    <a-tag :color="getStatusColor((task?.status as TaskStatus) || 'pending')">
      {{ $t(`ml.tuning.status.${task?.status || "pending"}`) }}
    </a-tag>
  </template>

  <!-- Metrics Column -->
  <template v-else-if="column.key === 'metrics'">
    <div
      v-if="task?.status === 'completed' && (task.result as any)?.metrics"
      class="text-sm"
    >
      <div
        v-for="(value, key) in getDisplayMetrics((task.result as any).metrics)"
        :key="key"
        class="inline-block mr-3"
      >
        <span class="text-gray-600">{{ formatMetricKey(key) }}:</span>
        <span class="ml-1 font-medium">{{ formatMetric(value) }}</span>
      </div>
    </div>
    <span v-else-if="task?.status === 'failed'" class="text-red-500 text-sm">
      {{ task.error || "Training failed" }}
    </span>
    <span v-else-if="task?.status === 'running'" class="text-blue-500 text-sm">
      {{ $t("ml.tuning.training") }}
    </span>
    <span v-else class="text-gray-400 text-sm">-</span>
  </template>

  <!-- Actions Column -->
  <template v-else-if="column.key === 'action'">
    <div class="flex items-center gap-2">
      <a-radio
        :checked="isSelected"
        :disabled="task?.status !== 'completed'"
        @click="handleSelect"
      >
        {{ $t("ml.tuning.select") }}
      </a-radio>
      <a-button
        v-if="
          task?.status === 'completed' &&
          (task.result as any)?.params &&
          Object.keys((task.result as any).params).length > 0
        "
        size="small"
        class="inline-flex items-center"
        @click="handleViewParams"
      >
        <span class="i-mdi-eye-outline mr-1"></span>
        {{ $t("ml.tuning.viewParams") }}
      </a-button>
    </div>
  </template>
</template>

<script setup lang="ts">
import { useQuery } from "@tanstack/vue-query";

import type { Task, TaskStatus } from "@xenix/shared";

import { client } from "../../../../services/api-client";
import { useTaskFormatting } from "../../../../hooks";

interface Props {
  taskId: number;
  isSelected: boolean;
  column: { key: string };
}

const props = defineProps<Props>();

const emit = defineEmits<{
  select: [taskId: number];
  "view-params": [task: Task];
}>();

// Adaptive polling based on task status
const { data: task } = useQuery({
  queryKey: ["task", props.taskId],
  queryFn: async () => {
    const response = await client.tasks[":id"].$get({
      param: { id: String(props.taskId) },
    });
    if (!response.ok) throw new Error("Failed to fetch task");
    return response.json();
  },
  refetchInterval: (query) => {
    const task = query.state.data;
    if (!task) return false;
    if (task.status === "pending") return 2000; // 2s for pending
    if (task.status === "running") return 10000; // 10s for running
    return false; // Stop polling when completed/failed
  },
});

const {
  formatModelName,
  formatMetricKey,
  formatMetric,
  getDisplayMetrics,
  getStatusColor,
} = useTaskFormatting();

const handleSelect = () => {
  emit("select", props.taskId);
};

const handleViewParams = () => {
  if (task.value) {
    emit("view-params", task as unknown as Task);
  }
};
</script>
