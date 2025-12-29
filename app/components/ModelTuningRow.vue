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
          {{ t("tuning.manualTrain") }}
        </a-button>
      </div>
    </td>
    
    <!-- Metrics Column -->
    <td class="px-4 py-2"></td>
  </tr>
  
  <!-- Child rows (training history) -->
  <tr
    v-for="task in displayedHistory"
    :key="`${modelName}-${task.taskId}`"
    class="bg-gray-50 border-b"
  >
    <!-- Select Column -->
    <td class="px-4 py-2 text-center">
      <a-radio
        :checked="selectedTaskId === task.taskId"
        @click="$emit('update:selectedTaskId', task.taskId)"
      />
    </td>
    
    <!-- Model Name / Timestamp Column -->
    <td class="px-4 py-2">
      <span class="font-medium pl-2">
        {{ formatTimestamp(task.createdAt) }}
      </span>
    </td>
    
    <!-- Tune Type Column -->
    <td class="px-4 py-2">
      <div class="text-sm">
        <div class="font-medium mb-1">
          <a-tag v-if="task.trainingType === 'auto-tune'" color="blue">
            {{ t("tuning.autoTune") }}
          </a-tag>
          <a-tag v-else-if="task.trainingType === 'train'" color="green">
            {{ t("tuning.manualTrain") }}
          </a-tag>
        </div>
        <div v-if="task.params" class="text-xs text-gray-600">
          <div
            v-for="(value, key) in task.params"
            :key="key"
            class="truncate"
          >
            <span class="font-medium">{{ key }}:</span>
            {{ formatParamValue(value) }}
          </div>
        </div>
      </div>
    </td>
    
    <!-- Action Column -->
    <td class="px-4 py-2">
      <div class="flex gap-2 items-center">
        <a-button
          v-if="task.taskId"
          size="small"
          @click="handleViewLogs(task.taskId)"
          class="inline-flex items-center"
        >
          <span class="i-mdi-text-box-outline mr-1" />
          {{ t("tuning.viewLogs") }}
        </a-button>
        <a-tag v-if="task.status" :color="getStatusColor(task.status)">
          {{ task.status }}
        </a-tag>
      </div>
    </td>
    
    <!-- Metrics Column -->
    <td class="px-4 py-2">
      <div v-if="task.metrics" class="text-sm">
        <div>
          <span class="font-medium">{{ t("metrics.r2") }}:</span>
          {{ formatMetric(task.metrics.r2_test) }}
        </div>
        <div>
          <span class="font-medium">{{ t("metrics.mse") }}:</span>
          {{ formatMetric(task.metrics.mse_test) }}
        </div>
        <div>
          <span class="font-medium">{{ t("metrics.mae") }}:</span>
          {{ formatMetric(task.metrics.mae_test) }}
        </div>
      </div>
      <span v-else class="text-gray-400">{{ t("common.na") }}</span>
    </td>
  </tr>

  <!-- Dialogs (using teleport to move them outside the table) -->
  <teleport to="body">
    <ParamGridDialog
      v-model="paramGridDialogVisible"
      :model-name="modelName"
      :model-label="modelLabel"
      :schema="currentModelSchema"
      :initial-values="paramGridValues"
      @save="handleSaveAutoTune"
    />

    <ManualTrainDialog
      v-model="manualTrainDialogVisible"
      :model-name="modelName"
      :model-label="modelLabel"
      :schema="currentModelSchema"
      :initial-values="manualTrainValues"
      @train="handleSaveManualTrain"
    />

    <a-modal
      v-model:open="logModalVisible"
      :title="t('logs.titleWithModel', { model: modelLabel })"
      width="800px"
      :footer="null"
    >
      <LogPanel :logs="currentLogs" />
    </a-modal>
  </teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { TaskService, ModelService } from "~/services";
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
const trainingHistory = ref<any[]>([]);
const taskLogs = ref<Record<string, any[]>>({});
const currentTaskId = ref<number | null>(null);

// Dialog states
const paramGridDialogVisible = ref(false);
const manualTrainDialogVisible = ref(false);
const logModalVisible = ref(false);

// Model metadata
const modelMetadata = ref<any>(null);
const paramGridValues = ref<Record<string, any>>({});
const manualTrainValues = ref<Record<string, any>>({});

// Computed properties
const currentModelSchema = computed(() => {
  return modelMetadata.value?.paramGridSchema || null;
});

const currentLogs = computed(() => {
  if (!currentTaskId.value) return [];
  return taskLogs.value[currentTaskId.value] || [];
});

const displayedHistory = computed(() => {
  return props.isExpanded ? trainingHistory.value : [];
});

// Fetch model metadata
const fetchModelMetadata = async () => {
  try {
    const response = await ModelService.fetchMetadata();
    if (response.success && response.models) {
      const metadata = response.models.find((m: any) => m.name === props.modelName);
      if (metadata) {
        modelMetadata.value = metadata;
      }
    }
  } catch (error) {
    console.error(`Failed to fetch metadata for ${props.modelName}:`, error);
  }
};

// Fetch training history
const fetchTrainingHistory = async () => {
  try {
    const response = await TaskService.fetchTrainingHistory(props.modelName);
    if (response.success && response.results) {
      trainingHistory.value = response.results;
    }
  } catch (error) {
    console.error(`Failed to fetch training history for ${props.modelName}:`, error);
  }
};

// Fetch task logs
const fetchTaskLogs = async (taskId: number) => {
  try {
    const response = await TaskService.fetchLogs(taskId);
    if (response.success && response.logs) {
      taskLogs.value[taskId] = response.logs;
    }
  } catch (error) {
    console.error(`Failed to fetch logs for task ${taskId}:`, error);
  }
};

// Event handlers
const handleAutoTune = () => {
  paramGridDialogVisible.value = true;
};

const handleManualTrain = () => {
  manualTrainDialogVisible.value = true;
};

const handleViewLogs = (taskId: number) => {
  currentTaskId.value = taskId;
  logModalVisible.value = true;
  fetchTaskLogs(taskId);
};

const handleSaveAutoTune = (values: Record<string, any>) => {
  paramGridValues.value = values;
  emit("start-tune", props.modelName, values, "auto");
};

const handleSaveManualTrain = (values: Record<string, any>) => {
  manualTrainValues.value = values;
  // Find the most recent task for this model as parent
  const parentTaskId = trainingHistory.value[0]?.taskId || null;
  emit("start-tune", props.modelName, values, "manual", parentTaskId || undefined);
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
    if (expanded && trainingHistory.value.length === 0) {
      fetchTrainingHistory();
    }
  },
  { immediate: true }
);

// Initialize
onMounted(() => {
  fetchModelMetadata();
  if (props.isExpanded) {
    fetchTrainingHistory();
  }
});
</script>

<style scoped>
.rotate-90 {
  transform: rotate(90deg);
}
</style>
