/**
 * Composable for managing upload step logic
 * Handles file upload, dataset selection, and column configuration
 */

import { ref } from "vue";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";
import { DatasetService } from "~/services";
import { useFileUpload } from "./useFileUpload";
import type { Dataset } from "~/types";

export function useUploadStep(projectId?: number) {
  const { t } = useI18n();
  const { isLoadingColumns, readExcelColumns, validateExcelFile } = useFileUpload();

  // Dataset state
  const datasets = ref<Dataset[]>([]);
  const isLoadingDatasets = ref(false);
  const selectedDatasetId = ref<number | undefined>(undefined);
  const selectedDataset = ref<Dataset | null>(null);

  // File upload state
  const fileList = ref<any[]>([]);

  // Column selection state
  const showColumnSelection = ref(false);
  const excelColumns = ref<string[]>([]);
  const selectedFeatureColumns = ref<string[]>([]);
  const selectedTargetColumn = ref<string | undefined>(undefined);

  /**
   * Fetch available datasets
   */
  const fetchDatasets = async () => {
    isLoadingDatasets.value = true;
    try {
      if (projectId) {
        const projectResponse = await $fetch(`/api/projects/${projectId}`);
        if (projectResponse.success) {
          datasets.value = projectResponse.project.datasets || [];
        }
      } else {
        const response = await DatasetService.fetchAll();
        if (response.success) {
          datasets.value = response.datasets;
        }
      }
    } catch (error) {
      console.error("Failed to fetch datasets:", error);
    } finally {
      isLoadingDatasets.value = false;
    }
  };

  /**
   * Filter dataset options in select dropdown
   */
  const filterDatasetOption = (input: string, option: any) => {
    const dataset = datasets.value.find((d) => d.id === option.value);
    if (!dataset) return false;
    return dataset.name.toLowerCase().includes(input.toLowerCase());
  };

  /**
   * Handle dataset selection from dropdown
   */
  const handleDatasetSelected = (datasetId: number) => {
    selectedDataset.value = datasets.value.find((d) => d.id === datasetId) || null;
    fileList.value = [];
  };

  /**
   * Validate file before upload
   */
  const beforeUpload = (file: File) => {
    if (!validateExcelFile(file)) {
      return false;
    }
    selectedDatasetId.value = undefined;
    selectedDataset.value = null;
    return false; // Prevent auto upload
  };

  /**
   * Continue to column selection with selected dataset
   */
  const handleDatasetContinue = async () => {
    if (!selectedDataset.value) {
      message.error(t("datasets.selectDatasetError"));
      return;
    }

    excelColumns.value = selectedDataset.value.columns;
    showColumnSelection.value = true;
    message.success(
      t("datasets.columnsFound", { count: selectedDataset.value.columns.length })
    );
  };

  /**
   * Continue to column selection with uploaded file
   */
  const handleFileUploadedContinue = async () => {
    if (fileList.value.length === 0) {
      message.error(t("upload.noFileError"));
      return;
    }

    const file = fileList.value[0].originFileObj;
    const columns = await readExcelColumns(file);

    if (columns.length > 0) {
      excelColumns.value = columns;
      showColumnSelection.value = true;
    }
  };

  /**
   * Handle continue button click
   */
  const handleContinue = async () => {
    if (selectedDatasetId.value) {
      await handleDatasetContinue();
    } else if (fileList.value.length > 0) {
      await handleFileUploadedContinue();
    } else {
      message.error(t("upload.selectDatasetOrFile"));
    }
  };

  /**
   * Go back to file/dataset selection
   */
  const handleBackToUpload = () => {
    showColumnSelection.value = false;
    selectedFeatureColumns.value = [];
    selectedTargetColumn.value = undefined;
  };

  /**
   * Reset upload step state
   */
  const resetUploadStep = () => {
    fileList.value = [];
    selectedDatasetId.value = undefined;
    selectedDataset.value = null;
    showColumnSelection.value = false;
    excelColumns.value = [];
    selectedFeatureColumns.value = [];
    selectedTargetColumn.value = undefined;
  };

  return {
    // State
    datasets,
    isLoadingDatasets,
    selectedDatasetId,
    selectedDataset,
    fileList,
    showColumnSelection,
    excelColumns,
    selectedFeatureColumns,
    selectedTargetColumn,
    isLoadingColumns,

    // Actions
    fetchDatasets,
    filterDatasetOption,
    handleDatasetSelected,
    beforeUpload,
    handleContinue,
    handleBackToUpload,
    resetUploadStep,
  };
}
