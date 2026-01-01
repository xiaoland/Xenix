<template>
  <!-- Parent row -->
  <tr class="border-b hover:bg-gray-50">
    <!-- Model Name Column -->
    <td class="px-4 py-2">
      <span class="font-medium">{{
        $t(`models.${model.replace(".", "_")}`)
      }}</span>
    </td>

    <!-- Action Column -->
    <td class="px-4 py-2">
      <div class="flex gap-2">
        <a-button
          type="primary"
          size="small"
          @click="handleAutoTune"
          class="inline-flex items-center tune-btn"
        >
          <span class="i-mdi-tune mr-1" />
          {{ t("tuning.autoTune") }}
        </a-button>
        <a-button
          size="small"
          @click="handleManualTrain"
          class="inline-flex items-center tune-btn"
        >
          <span class="i-mdi-pencil mr-1" />
          {{ t("tuning.manualTune") }}
        </a-button>
      </div>
    </td>

    <!-- Metrics Column (empty for parent row) -->
    <td class="px-4 py-2"></td>
  </tr>

  <!-- Child rows (tuning tasks) -->
  <ModelTuningSubRow
    v-for="taskId in displayedTaskIds"
    :key="`${model}-${taskId}`"
    :task-id="taskId"
    v-model:selectedTaskId="selectedTaskIdProxy"
  />

  <!-- Dialogs (using teleport to move them outside the table) -->
  <teleport to="body">
    <AutoTuneDialog
      v-model="autoTuneDialogVisible"
      :model="model"
      @create-task="handleCreateAutoTuneTask"
    />

    <ManualTuneDialog
      v-model="manualTuneDialogVisible"
      :model="model"
      @tune="handleManualTune"
    />
  </teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { WorkItemService, TuneService, TaskService } from "~/services";
import ModelTuningSubRow from "./ModelTuningSubRow.vue";
import ManualTuneDialog from "./ManualTuneDialog.vue";
import AutoTuneDialog from "./AutoTuneDialog.vue";

const { t } = useI18n();

const props = defineProps<{
  model: string;
  workItemId: number;
  selectedTaskId: number | null;
  refreshTrigger: number;
}>();

const emit = defineEmits<{
  "update:selectedTaskId": [taskId: number | null];
}>();

// Compute model label from model value
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
  return taskIds.value;
});

// Fetch task IDs for this model from work item
const fetchTaskIds = async () => {
  try {
    const response = await TaskService.fetchByWorkItemId(props.workItemId, [
      "manual-tune",
      "auto-tune",
    ]);
    if (response.success && response.tasks) {
      // Filter tasks for this model
      const modelTasks = response.tasks
        .filter((task: any) => {
          const param = task.parameter || {};
          return param.model === props.model;
        })
        .map((task: any) => task.id);

      taskIds.value = modelTasks;
    }
  } catch (error) {
    console.error(`Failed to fetch task IDs for ${props.model}:`, error);
  }
};

// Event handlers
const handleAutoTune = () => {
  autoTuneDialogVisible.value = true;
};

const handleManualTrain = () => {
  manualTuneDialogVisible.value = true;
};

const handleCreateAutoTuneTask = async (paramGrid: Record<string, any>) => {
  try {
    // Get work item to extract dataset and feature info
    const workItem = await WorkItemService.fetchById(props.workItemId);
    if (workItem.success && workItem.workItem) {
      const { datasetId, features, target } = workItem.workItem;

      await TuneService.startAutoTune({
        datasetId: String(datasetId),
        features: features || [],
        target: target || "",
        model: props.model,
        paramGrid,
        workItemId: props.workItemId,
      });

      autoTuneDialogVisible.value = false;
      // Refresh task list
      await fetchTaskIds();
    }
  } catch (error) {
    console.error("Failed to start auto-tune:", error);
  }
};

const handleManualTune = async (parameters: Record<string, any>) => {
  try {
    await TuneService.startManualTune({
      model: props.model,
      parameters,
      workItemId: props.workItemId,
    });

    manualTuneDialogVisible.value = false;
    // Refresh task list
    await fetchTaskIds();
  } catch (error) {
    console.error("Failed to start manual tune:", error);
  }
};

// Initialize
onMounted(() => {
  fetchTaskIds();
});

// Watch for refresh trigger to re-fetch tasks
watch(
  () => props.refreshTrigger,
  () => {
    fetchTaskIds();
  }
);
</script>

<style scoped>
.rotate-90 {
  transform: rotate(90deg);
}

.tune-btn {
  min-width: 70px;
  justify-content: center;
}
</style>
