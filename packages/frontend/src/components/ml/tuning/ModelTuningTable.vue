<template>
  <div class="bg-white rounded-lg border">
    <div class="px-4 py-3 border-b bg-gray-50">
      <h3 class="text-lg font-medium">
        {{ $t("ml.tuning.trainingTasks") }}
      </h3>
    </div>

    <a-table
      :columns="columns"
      :data-source="tasks"
      :loading="loading"
      :pagination="false"
      row-key="id"
      size="small"
    >
      <template #bodyCell="{ column, record }">
        <ModelTuningRow
          :task-id="record.id"
          :is-selected="selectedTaskId === record.id"
          :column="column"
          @select="handleSelectTask"
          @view-params="handleViewParams"
        />
      </template>
    </a-table>

    <div
      v-if="tasks?.length === 0 && !loading"
      class="text-center py-8 text-gray-500"
    >
      {{ $t("ml.tuning.noTasks") }}
    </div>

    <!-- View Params Modal -->
    <TaskParamsModal
      v-model:open="showParamsModal"
      :task="selectedTaskForParams"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";

import type { Task } from "@xenix/shared";

import { useTasks } from "@/composables";

import ModelTuningRow from "./ModelTuningRow.vue";
import TaskParamsModal from "./TaskParamsModal.vue";

interface Props {
  workItemId: number;
  selectedTaskId: number | null;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  "select-task": [taskId: number];
}>();

// Fetch tasks once on mount - NO polling at table level
const {
  data: tasks,
  isLoading: loading,
  refetch,
} = useTasks(
  {
    workItemId: String(props.workItemId),
    type: "batch-train,single-train",
  },
  {
    refetchInterval: false, // Disable polling - ModelTuningRow handles updates
  },
);

// Expose refetch method to parent component
defineExpose({
  refetch,
});

// Local modal state
const showParamsModal = ref(false);
const selectedTaskForParams = ref<Task | null>(null);

// Table columns
const columns = [
  {
    title: "Model",
    key: "model",
    width: 180,
  },
  {
    title: "Type",
    key: "type",
    width: 80,
  },
  {
    title: "Status",
    key: "status",
    width: 100,
  },
  {
    title: "Metrics",
    key: "metrics",
  },
  {
    title: "Actions",
    key: "action",
    width: 200,
  },
];

const handleSelectTask = (taskId: number) => {
  emit("select-task", taskId);
};

const handleViewParams = (task: Task) => {
  selectedTaskForParams.value = task;
  showParamsModal.value = true;
};
</script>
