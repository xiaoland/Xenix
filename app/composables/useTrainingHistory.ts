import { ref, watch } from "vue";

/**
 * Composable for managing training history data fetching and state
 */
export function useTrainingHistory(tuningResults: any) {
  const trainingHistory = ref<Record<string, any[]>>({});
  const expandedKeys = ref<string[]>([]);

  // Fetch training history for a specific model
  const fetchTrainingHistory = async (model: string) => {
    try {
      const response = await $fetch(`/api/results/history/${model}`);
      if (response.success && response.results) {
        trainingHistory.value[model] = response.results;
      }
    } catch (error) {
      console.error(`Failed to fetch training history for ${model}:`, error);
    }
  };

  // Handle row expansion
  const handleExpand = (expanded: boolean, record: any) => {
    if (expanded) {
      if (!expandedKeys.value.includes(record.model)) {
        expandedKeys.value.push(record.model);
      }
      // Fetch history when expanding
      fetchTrainingHistory(record.model);
    } else {
      expandedKeys.value = expandedKeys.value.filter((key) => key !== record.model);
    }
  };

  // Fetch training history when results change
  watch(
    tuningResults,
    async () => {
      // Fetch history for each model that has results
      for (const result of tuningResults.value) {
        await fetchTrainingHistory(result.model);
      }
    },
    { immediate: true, deep: true }
  );

  return {
    trainingHistory,
    expandedKeys,
    fetchTrainingHistory,
    handleExpand,
  };
}
