<template>
  <div>
    <h3 class="text-lg font-medium mb-3">
      {{ $t("tuning.modelSelectionAndTuning") }}
    </h3>
    
    <!-- Model Selector and Add Button -->
    <div class="mb-4 flex gap-2 items-center">
      <a-select
        v-model:value="selectedModelToAdd"
        :placeholder="t('tuning.selectModelToAdd')"
        class="w-64"
        :options="availableModelOptions"
      />
      <a-button
        type="primary"
        :disabled="!selectedModelToAdd || selectedModels.some(m => m.value === selectedModelToAdd)"
        @click="handleAddModel"
      >
        {{ t("tuning.addModel") }}
      </a-button>
    </div>
    
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
        <template v-for="model in selectedModels" :key="model.value">
          <ModelTuningRow
            :model="model.value"
            :work-item-id="workItemId"
            v-model:selectedTaskId="modelValue"
            :isTuning="isTuning"
            :isExpanded="expandedKeys.includes(model.value)"
            @toggle-expand="toggleExpand"
          />
        </template>
        <tr v-if="selectedModels.length === 0">
          <td colspan="5" class="px-4 py-8 text-center text-gray-500">
            {{ t("tuning.noModelsAdded") }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, toRef, computed } from "vue";
import { useI18n } from "vue-i18n";
import { WorkItemService } from "~/services";
import ModelTuningRow from "./ModelTuningRow.vue";
import { AVAILABLE_MODELS } from "~/constants/models";

const { t } = useI18n();

const props = defineProps<{
  workItemId: number;
}>();

const modelValue = defineModel<number | null>("selectedTaskId", {
  default: null,
});

const workItemIdRef = toRef(() => props.workItemId);

// Data states
const selectedModels = ref<Array<{ label: string; value: string }>>([]);
const isTuning = ref(false);
const selectedModelToAdd = ref<string | undefined>(undefined);

// UI states
const expandedKeys = ref<string[]>([]);

// Available model options (all models from constants that are not yet selected)
const availableModelOptions = computed(() => {
  return AVAILABLE_MODELS.filter(
    m => !selectedModels.value.some(sm => sm.value === m.value)
  ).map(m => ({
    label: m.label,
    value: m.value,
  }));
});

// Fetch selected models from work item
const fetchSelectedModels = async () => {
  if (!workItemIdRef.value) return;

  try {
    const response = await WorkItemService.fetchById(workItemIdRef.value);
    if (response.success && response.workItem) {
      const workItem = response.workItem;

      // Extract selected models from tasks
      const models = new Set<string>();
      if (workItem.tasks) {
        workItem.tasks.forEach((task: any) => {
          if (task.parameter?.model) {
            models.add(task.parameter.model);
          }
        });
      }

      // Build selected models list (use i18n translation if available)
      const modelsList = Array.from(models).map((model) => {
        const found = AVAILABLE_MODELS.find(m => m.value === model);
        return { 
          label: found?.label || t(`models.${model.replace(".", "_")}`),
          value: model 
        };
      });
      selectedModels.value = modelsList;

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
    console.error("Failed to fetch selected models:", error);
  }
};

// Add a new model to the table
const handleAddModel = () => {
  if (!selectedModelToAdd.value) return;
  
  // Check if already added
  if (availableModels.value.some(m => m.value === selectedModelToAdd.value)) {
    return;
  }
// Add a new model to the table
const handleAddModel = () => {
  if (!selectedModelToAdd.value) return;
  
  // Find the model from constants
  const modelToAdd = AVAILABLE_MODELS.find(m => m.value === selectedModelToAdd.value);
  if (modelToAdd) {
    selectedModels.value.push({
      label: modelToAdd.label,
      value: modelToAdd.value,
    });
  }
  
  // Clear selection
  selectedModelToAdd.value = undefined;
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

// Watch for workItemId changes and refetch data
watch(
  workItemIdRef,
  () => {
    if (workItemIdRef.value) {
      fetchSelectedModels();
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
