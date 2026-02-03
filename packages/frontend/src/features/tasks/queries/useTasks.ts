/**
 * Tasks Queries
 * TanStack Query hooks for task data fetching
 */
import { useQuery } from "@tanstack/vue-query";

import { client } from "@/services/api-client";
import { POLLING_CONFIG } from "@/constants/config";

export function useTasks(
  params?: { workItemId: string; type?: string },
  options?: { refetchInterval?: number | false },
) {
  return useQuery({
    queryKey: ["tasks", params],
    queryFn: async () => {
      const response = await client.tasks.$get({ query: params! });
      if (!response.ok) {
        throw new Error("Failed to fetch tasks");
      }
      return response.json();
    },
    refetchInterval: options?.refetchInterval ?? 5000,
    placeholderData: [],
  });
}

export function useTask(id: number | string) {
  return useQuery({
    queryKey: ["task", id],
    queryFn: async () => {
      const response = await client.tasks[":id"].$get({
        param: { id: String(id) },
      });
      if (!response.ok) {
        throw new Error("Failed to fetch task");
      }
      return response.json();
    },
    enabled: !!id,
    refetchInterval: (query) => {
      const task = query.state.data;
      if (task && (task.status === "pending" || task.status === "running")) {
        return POLLING_CONFIG.TASK_STATUS_INTERVAL;
      }
      return false;
    },
  });
}
