/**
 * Work Items Queries
 * TanStack Query hooks for work item data fetching
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import type { WorkItem } from "@xenix/shared";

import { client } from "@/services/api-client";

export function useWorkItems() {
  return useQuery({
    queryKey: ["work-items"],
    queryFn: async () => {
      const response = await client["work-items"].$get({});
      if (!response.ok) {
        throw new Error("Failed to fetch work items");
      }
      return response.json();
    },
  });
}

export function useWorkItem(id: number | string) {
  return useQuery({
    queryKey: ["work-item", id],
    queryFn: async () => {
      const response = await client["work-items"][":id"].$get({
        param: { id: String(id) },
      });
      if (!response.ok) {
        throw new Error("Failed to fetch work item");
      }
      return response.json();
    },
    enabled: !!id,
  });
}

export function useCreateWorkItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (workItem: {
      projectId: number;
      name: string;
      description?: string;
    }) => {
      const response = await client["work-items"].$post({
        json: workItem,
      });
      if (!response.ok) {
        throw new Error("Failed to create work item");
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["work-items"] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useUpdateWorkItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      updates,
    }: {
      id: number | string;
      updates: Partial<WorkItem>;
    }) => {
      const response = await client["work-items"][":id"].$put({
        param: { id: String(id) },
        json: updates,
      });
      if (!response.ok) {
        throw new Error("Failed to update work item");
      }
      return response.json();
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["work-items"] });
      queryClient.invalidateQueries({ queryKey: ["work-item", id] });
    },
  });
}

export function useDeleteWorkItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number | string) => {
      const response = await client["work-items"][":id"].$delete({
        param: { id: String(id) },
      });
      if (!response.ok) {
        throw new Error("Failed to delete work item");
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["work-items"] });
    },
  });
}
