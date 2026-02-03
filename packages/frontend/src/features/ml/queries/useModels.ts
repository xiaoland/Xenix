/**
 * Models Queries
 * TanStack Query hooks for ML model data fetching
 */
import { computed } from "vue";
import { useQuery } from "@tanstack/vue-query";

import type { ModelOption } from "@xenix/shared";

import { client } from "@/services/api-client";

interface ModelGroupOption {
  label: string;
  options: ModelOption[];
}

export function useModels() {
  return useQuery({
    queryKey: ["models"],
    queryFn: async () => {
      const response = await client.models.$get();
      if (!response.ok) {
        throw new Error("Failed to fetch models");
      }
      const models = await response.json();

      return models.map(
        (model): ModelOption => ({
          label: model.label,
          value: model.name,
        }),
      );
    },
    staleTime: Infinity,
    placeholderData: [],
  });
}

export function useGroupedModels() {
  const query = useQuery({
    queryKey: ["models"],
    queryFn: async () => {
      const response = await client.models.$get();
      if (!response.ok) {
        throw new Error("Failed to fetch models");
      }
      return response.json();
    },
    staleTime: Infinity,
    placeholderData: [],
  });

  const groupedModels = computed(() => {
    if (!query.data.value) return [];

    const groups: Record<string, ModelOption[]> = {};

    query.data.value.forEach((model) => {
      const category = model.category || "other";
      if (!groups[category]) {
        groups[category] = [];
      }
      groups[category].push({
        label: model.label,
        value: model.name,
      });
    });

    const categoryLabels: Record<string, string> = {
      regression: "Regression",
      classification: "Classification",
      clustering: "Clustering",
      other: "Other",
    };

    return Object.entries(groups).map(
      ([category, options]): ModelGroupOption => ({
        label: categoryLabels[category] || category,
        options,
      }),
    );
  });

  return {
    data: groupedModels,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}
