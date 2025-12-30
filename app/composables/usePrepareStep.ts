/**
 * Composable for managing prepare step logic
 * Handles feature and target column selection
 */

import { ref, computed } from "vue";
import { message } from "ant-design-vue";
import { useI18n } from "vue-i18n";

export function usePrepareStep() {
  const { t } = useI18n();

  // Column selection state
  const selectedFeatureColumns = ref<string[]>([]);
  const selectedTargetColumn = ref<string | undefined>(undefined);

  /**
   * Validate column selection
   */
  const isValid = computed(() => {
    return (
      selectedFeatureColumns.value.length > 0 &&
      selectedTargetColumn.value !== undefined
    );
  });

  /**
   * Reset column selection
   */
  const resetPrepareStep = () => {
    selectedFeatureColumns.value = [];
    selectedTargetColumn.value = undefined;
  };

  /**
   * Handle column selection confirmation
   */
  const handleColumnSelection = (data: {
    featureColumns: string[];
    targetColumn: string;
  }) => {
    selectedFeatureColumns.value = data.featureColumns;
    selectedTargetColumn.value = data.targetColumn;

    message.success(
      `${t("columns.selectedFeatures", {
        count: data.featureColumns.length,
      })} ${t("columns.targetSetTag")}`
    );
  };

  return {
    // State
    selectedFeatureColumns,
    selectedTargetColumn,

    // Computed
    isValid,

    // Actions
    resetPrepareStep,
    handleColumnSelection,
  };
}
