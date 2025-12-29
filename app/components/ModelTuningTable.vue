<template>
  <div>
    <h3 class="text-lg font-medium mb-3">
      {{ $t("tuning.modelSelectionAndTuning") }}
    </h3>
    <table class="w-full border-collapse model-tuning-table">
      <thead>
        <tr class="border-b bg-gray-50">
          <th class="px-4 py-2 text-left w-12"></th>
          <th class="px-4 py-2 text-left">{{ t("tuning.model") }}</th>
          <th class="px-4 py-2 text-left w-48">{{ t("tuning.tuneType") }}</th>
          <th class="px-4 py-2 text-left w-80">{{ t("tuning.tuning") }}</th>
          <th class="px-4 py-2 text-left w-80">{{ t("tuning.metrics") }}</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="model in availableModels" :key="model.value">
          <ModelTuningRow
            :model-name="model.value"
            :model-label="model.label"
            :work-item-id="workItemId"
            v-model:selectedTaskId="modelValue"
            :isTuning="isTuning"
            :isExpanded="expandedKeys.includes(model.value)"
            @start-tune="handleStartTune"
            @toggle-expand="toggleExpand"
          />
        </template>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, toRef } from "vue";
import { useI18n } from "vue-i18n";
import { WorkItemService } from "~/services";
import ModelTuningRow from "./ModelTuningRow.vue";

const { t } = useI18n();

const props = defineProps<{
  workItemId: number;
}>();

const modelValue = defineModel<number | null>("selectedTaskId", {
  default: null,
});

const emit = defineEmits<{
  "start-tune": [
    model: string,
    paramGrid?: Record<string, any>,
    trainingType?: string,
    parentTaskId?: number
  ];
  "view-logs": [taskId: number, modelName: string];
}>();

const workItemIdRef = toRef(() => props.workItemId);

// Data states
const availableModels = ref<Array<{ label: string; value: string }>>([]);
const isTuning = ref(false);

// UI states
const expandedKeys = ref<string[]>([]);

// Fetch available models from work item
const fetchAvailableModels = async () => {
  if (!workItemIdRef.value) return;

  try {
    const response = await WorkItemService.fetchById(workItemIdRef.value);
    if (response.success && response.workItem) {
      const workItem = response.workItem;

      // Extract available models from tasks or use defaults
      const models = new Set<string>();
      if (workItem.tasks) {
        workItem.tasks.forEach((task: any) => {
          if (task.parameter?.model) {
            models.add(task.parameter.model);
          }
        });
      }

      // Build available models list (use i18n translation if available)
      const modelsList = Array.from(models).map((model) => {
        const translated = t(`models.${model.replace(".", "_")}`);
        return { label: translated, value: model };
      });
      availableModels.value = modelsList;

      // Determine if tuning is in progress
      if (workItem.tasks) {
        const statusMap: Record<string, string> = {};
        for (const task of workItem.tasks as any[]) {
          const model = task.parameter?.model;
          if (model) {
            statusMap[model] = task.status || "pending";
          }
        }
        isTuning.value = Object.values(statusMap).some(
          (status) => status === "processing" || status === "pending"
        );
      }
    }
  } catch (error) {
    console.error("Failed to fetch available models:", error);
  }
};

// Toggle expand/collapse
const toggleExpand = (modelName: string) => {
  const index = expandedKeys.value.indexOf(modelName);
  if (index > -1) {
    expandedKeys.value.splice(index, 1);
  } else {
    expandedKeys.value.push(modelName);
  }
};

// Event handlers
const handleStartTune = (
  model: string,
  paramGrid?: Record<string, any>,
  trainingType?: string,
  parentTaskId?: number
) => {
  emit("start-tune", model, paramGrid, trainingType, parentTaskId);
};

// Watch for workItemId changes and refetch data
watch(
  workItemIdRef,
  () => {
    if (workItemIdRef.value) {
      fetchAvailableModels();
    }
  },
  { immediate: true }
);
</script>

<style scoped>
.model-tuning-table tr {
  transition: background-color 0.2s;
}

.model-tuning-table th {
  font-weight: 600;
  color: #374151;
}

.rotate-90 {
  transform: rotate(90deg);
}
</style>
