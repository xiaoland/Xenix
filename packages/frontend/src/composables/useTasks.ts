/**
 * Tasks Composable
 * Uses TanStack Query for data fetching and caching
 */

import { useQuery, useQueryClient } from '@tanstack/vue-query';
import { useAuthStore } from '../stores/auth';
import type { TaskInfo } from '@xenix/shared';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000';

export function useTasks() {
  const authStore = useAuthStore();

  return useQuery({
    queryKey: ['tasks'],
    queryFn: async (): Promise<TaskInfo[]> => {
      const response = await fetch(`${API_URL}/api/tasks`, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          authStore.logout();
        }
        throw new Error('Failed to fetch tasks');
      }

      const data = await response.json();
      return data.tasks || [];
    },
    enabled: authStore.isAuthenticated,
    refetchInterval: 5000, // Refetch every 5 seconds to get task updates
  });
}

export function useTask(id: number | string) {
  const authStore = useAuthStore();

  return useQuery({
    queryKey: ['task', id],
    queryFn: async (): Promise<TaskInfo> => {
      const response = await fetch(`${API_URL}/api/tasks/${id}`, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          authStore.logout();
        }
        throw new Error('Failed to fetch task');
      }

      const data = await response.json();
      return data.task;
    },
    enabled: authStore.isAuthenticated && !!id,
    refetchInterval: (query) => {
      const task = query.state.data;
      // Only refetch if task is pending or running
      if (task && (task.status === 'pending' || task.status === 'running')) {
        return 3000; // 3 seconds
      }
      return false; // Don't refetch if completed or failed
    },
  });
}
