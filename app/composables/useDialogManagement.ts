import { ref, computed, onMounted } from "vue";

/**
 * Composable for managing dialog states and model metadata
 */
export function useDialogManagement() {
  // Dialog visibility states
  const logModalVisible = ref(false);
  const paramGridDialogVisible = ref(false);
  const manualTrainDialogVisible = ref(false);

  // Current editing/viewing states
  const currentLogTaskId = ref<number>(0);
  const currentLogModelName = ref<string>("");
  const currentEditModel = ref<string>("");
  const currentEditModelLabel = ref<string>("");

  // Model metadata and parameter values
  const modelMetadata = ref<any[]>([]);
  const paramGridValues = ref<Record<string, Record<string, any>>>({});
  const manualTrainValues = ref<Record<string, Record<string, any>>>({});

  // Fetch model metadata on mount
  onMounted(async () => {
    try {
      const response = await $fetch("/api/models");
      if (response.success) {
        modelMetadata.value = response.models;
      }
    } catch (error) {
      console.error("Failed to fetch model metadata:", error);
    }
  });

  // Get schema for current model being edited
  const currentModelSchema = computed(() => {
    const metadata = modelMetadata.value.find(
      (m) => m.name === currentEditModel.value
    );
    return metadata?.paramGridSchema || null;
  });

  // Dialog action handlers
  const openAutoTuneDialog = (modelName: string, modelLabel: string) => {
    currentEditModel.value = modelName;
    currentEditModelLabel.value = modelLabel;
    paramGridDialogVisible.value = true;
  };

  const openManualTrainDialog = (modelName: string, modelLabel: string) => {
    currentEditModel.value = modelName;
    currentEditModelLabel.value = modelLabel;
    manualTrainDialogVisible.value = true;
  };

  const openLogModal = (taskId: number, modelName: string) => {
    currentLogTaskId.value = taskId;
    currentLogModelName.value = modelName;
    logModalVisible.value = true;
  };

  return {
    // Dialog visibility
    logModalVisible,
    paramGridDialogVisible,
    manualTrainDialogVisible,

    // Current states
    currentLogTaskId,
    currentLogModelName,
    currentEditModel,
    currentEditModelLabel,

    // Model data
    modelMetadata,
    currentModelSchema,
    paramGridValues,
    manualTrainValues,

    // Dialog actions
    openAutoTuneDialog,
    openManualTrainDialog,
    openLogModal,
  };
}
