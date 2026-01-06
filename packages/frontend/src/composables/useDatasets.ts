/**
 * Datasets Composable
 * Uses TanStack Query with Hono RPC client for type-safe data fetching
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/vue-query";
import { client } from "../api/client";

export function useDatasets() {
  return useQuery({
    queryKey: ["datasets"],
    queryFn: async () => {
      const response = await client.data.$get({});
      if (!response.ok) {
        throw new Error("Failed to fetch datasets");
      }
      const data = (await response.json()) as any;
      return data.datasets || [];
    },
  });
}

export function useDataset(id: number | string) {
  return useQuery({
    queryKey: ["dataset", id],
    queryFn: async () => {
      const response = await client.data[":id"].$get({
        param: { id: String(id) },
      });
      if (!response.ok) {
        throw new Error("Failed to fetch dataset");
      }
      const data = (await response.json()) as any;
      return data.dataset;
    },
    enabled: !!id,
  });
}

export function useUploadDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (formData: FormData) => {
      const response = await client.data.$post({
        body: formData,
      });
      if (!response.ok) {
        const error = (await response.json()) as any;
        throw new Error(error.error || "Failed to upload dataset");
      }
      const data = (await response.json()) as any;
      return data.dataset;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
  });
}

export function useDeleteDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number | string) => {
      const response = await client.data[":id"].$delete({
        param: { id: String(id) },
      });
      if (!response.ok) {
        throw new Error("Failed to delete dataset");
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
  });
}
