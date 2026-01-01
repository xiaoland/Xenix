<template>
  <div>
    <h3 class="text-lg font-medium mb-3">
      {{ $t("tuning.modelSelectionAndTuning") }}
    </h3>

    <!-- Model Selector and Actions -->
    <div class="flex items-center justify-between mb-4">
      <ModelSelector
        v-model:selectedModels="selectedModelValues"
        :availableModels="availableModels"
        :tuningStatus="tuningStatus"
      />
      <a-popconfirm
        :title="t('tuning.confirmClearFailedTasks')"
        :ok-text="t('common.confirm')"
        :cancel-text="t('common.cancel')"
        @confirm="handleClearFailedTasks"
      >
        <a-button danger size="small" class="inline-flex items-center">
          <span class="i-mdi-delete-outline mr-1" />
          {{ t("tuning.clearFailedTasks") }}
        </a-button>
      </a-popconfirm>
    </div>

    <div>
      <table class="w-full border-collapse model-tuning-table table-fixed">
        <thead>
          <tr class="border-b bg-gray-50">
            <th class="px-4 py-2 text-left w-20">{{ t("tuning.model") }}</th>
            <th class="px-4 py-2 text-left w-55">{{ t("tuning.tuning") }}</th>
            <th class="px-4 py-2 text-left">
              {{ t("tuning.metrics") }}
            </th>
          </tr>
        </thead>
        <tbody>
          <template v-for="model in selectedModels" :key="model.value">
            <ModelTuningRow
              :model="model.value"
              :work-item-id="workItemId"
              :refresh-trigger="refreshTrigger"
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
  </div>
</template>

<script setup lang="ts">
import { ref, watch, toRef, computed, onUnmounted } from "vue";
import { useI18n } from "vue-i18n";
import { message } from "ant-design-vue";
import { WorkItemService, TaskService } from "~/services";
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

// Refresh trigger for ModelTuningRow components
const refreshTrigger = ref(0);

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

      // Fetch tasks separately
      const tasksResponse = await TaskService.fetchByWorkItemId(
        workItemIdRef.value,
        ["manual-tune", "auto-tune"]
      );
      const tasks = tasksResponse.success ? tasksResponse.tasks : [];

      // Start with models stored in selectedModels field
      const models = new Set<string>(workItem.selectedModels || []);

      // Also extract selected models from tasks (for backward compatibility)
      tasks.forEach((task: any) => {
        if (task.parameter?.model) {
          models.add(task.parameter.model);
        }
      });

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
        console.error(
          `Failed to save selected models for work item ${workItemIdRef.value}:`,
          error
        );
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

// Handle clearing failed tasks
const handleClearFailedTasks = async () => {
  try {
    await TaskService.deleteFailedTasks(props.workItemId);
    message.success(t("tuning.failedTasksCleared"));
    // Refresh data by re-fetching selected models (which also refetches tasks)
    await fetchSelectedModels();
    // Trigger refresh for all ModelTuningRow components
    refreshTrigger.value++;
  } catch (error) {
    console.error("Failed to clear failed tasks:", error);
    message.error(t("tuning.clearFailedTasksError"));
  }
};
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
