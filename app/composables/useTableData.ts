import { computed } from "vue";

/**
 * Composable for managing table data structure with expandable rows
 */
export function useTableData(
  availableModels: any,
  tuningStatus: any,
  tuningTasks: any,
  tuningResults: any,
  trainingHistory: any
) {
  // Get row key for table
  const getRowKey = (record: any) => {
    return record.isHistory ? `${record.model}-${record.taskId}` : record.model;
  };

  // Combine all data sources into a single table data structure with expandable rows
  const tableData = computed(() => {
    const data: any[] = [];
    
    for (const model of availableModels.value) {
      const status = tuningStatus.value[model.value];
      const taskId = tuningTasks.value[model.value];
      const result = tuningResults.value.find((r: any) => r.model === model.value);

      // Build children array for expandable rows
      const children: any[] = [];
      
      // Add historical tasks
      const history = trainingHistory.value[model.value] || [];
      for (const historyItem of history) {
        children.push({
          model: model.value,
          label: model.label,
          taskId: historyItem.taskId,
          status: historyItem.status || "completed",
          metrics: {
            r2_test: historyItem.r2_test,
            mse_test: historyItem.mse_test,
            mae_test: historyItem.mae_test,
          },
          params: historyItem.params,
          trainingType: historyItem.trainingType || "auto",
          createdAt: historyItem.createdAt,
          isHistory: true,
        });
      }
      
      // Add the current active task ONLY if it's not already in history
      if (status && taskId) {
        const existsInHistory = history.some((h: any) => h.taskId === taskId);
        if (!existsInHistory) {
          children.push({
            model: model.value,
            label: model.label,
            taskId: taskId,
            status: status,
            metrics: result
              ? {
                  r2_test: result.r2_test,
                  mse_test: result.mse_test,
                  mae_test: result.mae_test,
                }
              : null,
            params: result?.params,
            trainingType: result?.trainingType || "auto",
            createdAt: result?.createdAt || new Date(),
            isHistory: true,
            isCurrent: true,
          });
        }
      }

      // Parent row with children
      const parentRow = {
        model: model.value,
        label: model.label,
        status: status,
        taskId: taskId,
        metrics: result
          ? {
              r2_test: result.r2_test,
              mse_test: result.mse_test,
              mae_test: result.mae_test,
            }
          : null,
        isHistory: false,
        children: children,
      };
      
      data.push(parentRow);
    }

    return data;
  });

  return {
    tableData,
    getRowKey,
  };
}
