/**
 * Tasks Composable
 * Uses TanStack Query with Hono RPC client for type-safe data fetching
 */

import { useQuery } from "@tanstack/vue-query";
import { client } from "../api/client";

export function useTasks() {
  return useQuery({
    queryKey: ["tasks"],
    queryFn: async () => {
      const response = await client.api.tasks.$get({});
      if (!response.ok) {
        throw new Error("Failed to fetch tasks");
      }
      const data = (await response.json()) as any;
      return data.tasks || [];
    },
    refetchInterval: 5000, // Refetch every 5 seconds to get task updates
  });
}

export function useTask(id: number | string) {
  return useQuery({
    queryKey: ["task", id],
    queryFn: async () => {
      const response = await client.api.tasks[":id"].$get({
        param: { id: String(id) },
      });
      if (!response.ok) {
        throw new Error("Failed to fetch task");
      }
      const data = (await response.json()) as any;
      return data.task;
    },
    enabled: !!id,
    refetchInterval: (query) => {
      const task = query.state.data;
      // Only refetch if task is pending or running
      if (task && (task.status === "pending" || task.status === "running")) {
        return 3000; // 3 seconds
      }
      return false; // Don't refetch if completed or failed
    },
  });
}
