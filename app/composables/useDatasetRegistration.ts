/**
 * Composable for managing dataset registration and upload
 */

import { ref } from "vue";
import { ApiService } from "~/services/apiService";
import { message } from "ant-design-vue";

export function useDatasetRegistration() {
  const uploadedDatasetId = ref<string>("");

  /**
   * Register a file as a dataset (auto-registration during training)
   */
  const registerFileAsDataset = async (
    file: File,
    existingDatasetId?: string
  ): Promise<string | null> => {
    // If we already have a dataset ID, use it
    if (existingDatasetId || uploadedDatasetId.value) {
      return existingDatasetId || uploadedDatasetId.value;
    }

    try {
      const datasetName = `Training Data - ${new Date().toLocaleString()}`;
      const response = await ApiService.registerDataset(
        file,
        datasetName,
        "Auto-registered during training"
      );

      if (response.success) {
        uploadedDatasetId.value = response.dataset.datasetId;
        message.success("Training data registered as reusable dataset");
        return response.dataset.datasetId;
      }
    } catch (error) {
      console.error("Failed to register dataset:", error);
    }

    return null;
  };

  /**
   * Reset dataset registration state
   */
  const clearDatasetId = () => {
    uploadedDatasetId.value = "";
  };

  return {
    uploadedDatasetId,
    registerFileAsDataset,
    clearDatasetId,
  };
}
