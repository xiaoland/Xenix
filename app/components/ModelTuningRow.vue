<template>
  <!-- Parent row -->
  <tr class="border-b hover:bg-gray-50">
    <!-- Expand icon -->
    <td class="px-4 py-2">
      <span
        class="inline-block transition-transform cursor-pointer"
        :class="{ 'rotate-90': isExpanded }"
        @click.stop="$emit('toggle-expand', modelName)"
      >
        ▶
      </span>
    </td>

    <!-- Model Name Column -->
    <td class="px-4 py-2">
      <span class="font-medium">{{ modelLabel }}</span>
    </td>

    <!-- Tune Type Column -->
    <td class="px-4 py-2"></td>

    <!-- Action Column -->
    <td class="px-4 py-2">
      <div class="flex gap-2">
        <a-button
          type="primary"
          size="small"
          :disabled="isTuning"
          @click="handleAutoTune"
          class="inline-flex items-center"
        >
          <span class="i-mdi-tune mr-1" />
          {{ t("tuning.autoTune") }}
        </a-button>
        <a-button
          size="small"
          :disabled="isTuning"
          @click="handleManualTrain"
          class="inline-flex items-center"
        >
          <span class="i-mdi-pencil mr-1" />
          {{ t("tuning.manualTune") }}
        </a-button>
      </div>
    </td>
  </tr>

  <!-- Child rows (tuning tasks) -->
  <ModelTuningSubRow
    v-for="taskId in displayedTaskIds"
    :key="`${modelName}-${taskId}`"
    :task-id="taskId"
    v-model:selectedTaskId="selectedTaskIdProxy"
  />

  <!-- Dialogs (using teleport to move them outside the table) -->
  <teleport to="body">
    <AutoTuneDialog
      v-model="autoTuneDialogVisible"
      :model-name="modelName"
      :model-label="modelLabel"
      @create-task="handleCreateAutoTuneTask"
    />

    <ManualTuneDialog
      v-model="manualTuneDialogVisible"
      :model-name="modelName"
      :model-label="modelLabel"
      @tune="handleManualTune"
    />
  </teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { WorkItemService } from "~/services";
import { useFormatters } from "~/composables/useFormatters";

const { t } = useI18n();
const { formatTimestamp, formatMetric, getStatusColor } = useFormatters();

const props = defineProps<{
  modelName: string;
  modelLabel: string;
  workItemId: number;
  selectedTaskId: number | null;
  isTuning: boolean;
  isExpanded: boolean;
}>();

const emit = defineEmits<{
  "update:selectedTaskId": [taskId: number | null];
  "start-tune": [
    model: string,
    paramGrid?: Record<string, any>,
    trainingType?: string,
    parentTaskId?: number
  ];
  "toggle-expand": [modelName: string];
}>();

// Local state
const taskIds = ref<number[]>([]);

// Dialog states
const autoTuneDialogVisible = ref(false);
const manualTuneDialogVisible = ref(false);

// Computed properties
const selectedTaskIdProxy = computed({
  get: () => props.selectedTaskId,
  set: (value) => emit("update:selectedTaskId", value),
});

const displayedTaskIds = computed(() => {
  return props.isExpanded ? taskIds.value : [];
});

// Fetch task IDs for this model from work item
const fetchTaskIds = async () => {
  try {
    const response = await WorkItemService.fetchById(props.workItemId);
    if (response.success && response.workItem && response.workItem.tasks) {
      // Filter tasks for this model
      const modelTasks = response.workItem.tasks
        .filter((task: any) => {
          const param = task.parameter || {};
          return param.model === props.modelName;
        })
        .map((task: any) => task.id);

      taskIds.value = modelTasks;
    }
  } catch (error) {
    console.error(`Failed to fetch task IDs for ${props.modelName}:`, error);
  }
};

// Event handlers
const handleAutoTune = () => {
  autoTuneDialogVisible.value = true;
};

const handleManualTrain = () => {
  manualTuneDialogVisible.value = true;
};

const handleCreateAutoTuneTask = (values: Record<string, any>) => {
  emit("start-tune", props.modelName, values, "auto");
};

const handleManualTune = (values: Record<string, any>) => {
  // Find the most recent task for this model as parent
  const parentTaskId = taskIds.value[0] || null;
  emit(
    "start-tune",
    props.modelName,
    values,
    "manual",
    parentTaskId || undefined
  );
};

const formatParamValue = (value: any): string => {
  if (Array.isArray(value)) {
    return `[${value.join(", ")}]`;
  }
  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value);
  }
  return String(value);
};

// Watch for expansion changes to fetch data
watch(
  () => props.isExpanded,
  (expanded) => {
    if (expanded && taskIds.value.length === 0) {
      fetchTaskIds();
    }
  },
  { immediate: true }
);

// Initialize
onMounted(() => {
  if (props.isExpanded) {
    fetchTaskIds();
  }
});
</script>

<style scoped>
.rotate-90 {
  transform: rotate(90deg);
}
</style>
