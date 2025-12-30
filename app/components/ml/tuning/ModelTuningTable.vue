<template>
  <div>
    <h3 class="text-lg font-medium mb-3">
      {{ $t("tuning.modelSelectionAndTuning") }}
    </h3>

    <!-- Reuse ModelSelector to manage available model options -->
    <div class="mb-4">
      <ModelSelector
        v-model:selectedModels="selectedModelValues"
        :availableModels="availableModels"
        :tuningStatus="tuningStatus"
      />
    </div>

    <table class="w-full border-collapse model-tuning-table">
      <thead>
        <tr class="border-b bg-gray-50">
          <th class="px-4 py-2 text-left w-30">{{ t("tuning.model") }}</th>
          <th class="px-4 py-2 text-left w-48">{{ t("tuning.tuning") }}</th>
          <th class="px-4 py-2 text-left w-48">{{ t("tuning.tuneType") }}</th>
          <th class="px-4 py-2 text-left w-80">{{ t("tuning.metrics") }}</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="model in selectedModels" :key="model.value">
          <ModelTuningRow
            :model="model.value"
            :work-item-id="workItemId"
            v-model:selectedTaskId="modelValue"
          />
        </template>
        <tr v-if="selectedModels.length === 0">
          <td colspan="4" class="px-4 py-8 text-center text-gray-500">
            {{ t("tuning.noModelsAdded") }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, toRef, computed, onUnmounted } from "vue";
import { useI18n } from "vue-i18n";
import { WorkItemService } from "~/services";
import ModelTuningRow from "./ModelTuningRow.vue";
import { AVAILABLE_MODELS } from "~/constants/models";
import ModelSelector from "../ModelSelector.vue";

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
// ModelSelector manages the list of selected model values (string[])
const selectedModelValues = ref<string[]>([]);

// Optional tuning status per model (placeholder - could be populated from tasks)
const tuningStatus = ref<Record<string, string>>({});

// UI states

// Available model options (all models from constants)
const availableModels = computed(() => {
  return AVAILABLE_MODELS.map((m) => ({ label: m.label, value: m.value }));
});

// Fetch selected models from work item
const fetchSelectedModels = async () => {
  if (!workItemIdRef.value) return;

  try {
    const response = await WorkItemService.fetchById(workItemIdRef.value);
    if (response.success && response.workItem) {
      const workItem = response.workItem;

      // Start with models stored in selectedModels field
      const models = new Set<string>(workItem.selectedModels || []);
      
      // Also extract selected models from tasks (for backward compatibility)
      if (workItem.tasks) {
        workItem.tasks.forEach((task: any) => {
          if (task.parameter?.model) {
            models.add(task.parameter.model);
          }
        });
      }

      // Build selected models list (use i18n translation if available)
      const modelsList = Array.from(models).map((model) => {
        const found = AVAILABLE_MODELS.find((m) => m.value === model);
        return {
          label: found?.label || t(`models.${model.replace(".", "_")}`),
          value: model,
        };
      });
      selectedModels.value = modelsList;
      // synchronize values for ModelSelector
      selectedModelValues.value = modelsList.map((m) => m.value);
    }
  } catch (error) {
    console.error("Failed to fetch selected models:", error);
  }
};

// When ModelSelector changes the selected model values, update selectedModels
watch(
  selectedModelValues,
  (vals) => {
    selectedModels.value = vals.map((val) => {
      const found = AVAILABLE_MODELS.find((m) => m.value === val);
      return {
        label: found?.label || t(`models.${val.replace(".", "_")}`),
        value: val,
      };
    });
  },
  { immediate: false }
);

// Debounce timer for saving selected models
let saveModelsTimeout: ReturnType<typeof setTimeout> | null = null;

// Save selected models to work item whenever they change (debounced)
watch(
  selectedModelValues,
  async (vals) => {
    if (!workItemIdRef.value) return;
    
    // Clear any pending save operation
    if (saveModelsTimeout) {
      clearTimeout(saveModelsTimeout);
    }
    
    // Debounce the save operation by 500ms
    saveModelsTimeout = setTimeout(async () => {
      try {
        await WorkItemService.update(workItemIdRef.value, {
          selectedModels: vals,
        });
      } catch (error) {
        console.error(`Failed to save selected models for work item ${workItemIdRef.value}:`, error);
      }
    }, 500);
  },
  { immediate: false }
);

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

// Cleanup: Clear the debounce timeout when component is unmounted
onUnmounted(() => {
  if (saveModelsTimeout) {
    clearTimeout(saveModelsTimeout);
  }
});
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
