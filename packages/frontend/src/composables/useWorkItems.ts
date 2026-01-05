/**
 * Work Items Composable
 * Uses TanStack Query for data fetching and caching
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { useAuthStore } from '../stores/auth';
import type { WorkItem } from '@xenix/shared';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000';

export function useWorkItems() {
  const authStore = useAuthStore();

  return useQuery({
    queryKey: ['work-items'],
    queryFn: async (): Promise<WorkItem[]> => {
      const response = await fetch(`${API_URL}/api/work-items`, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          authStore.logout();
        }
        throw new Error('Failed to fetch work items');
      }

      const data = await response.json();
      return data.workItems || [];
    },
    enabled: authStore.isAuthenticated,
  });
}

export function useWorkItem(id: number | string) {
  const authStore = useAuthStore();

  return useQuery({
    queryKey: ['work-item', id],
    queryFn: async (): Promise<WorkItem> => {
      const response = await fetch(`${API_URL}/api/work-items/${id}`, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          authStore.logout();
        }
        throw new Error('Failed to fetch work item');
      }

      const data = await response.json();
      return data.workItem;
    },
    enabled: authStore.isAuthenticated && !!id,
  });
}

export function useCreateWorkItem() {
  const authStore = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (workItem: {
      projectId: number;
      name: string;
      description?: string;
    }): Promise<WorkItem> => {
      const response = await fetch(`${API_URL}/api/work-items`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.token}`,
        },
        body: JSON.stringify(workItem),
      });

      if (!response.ok) {
        if (response.status === 401) {
          authStore.logout();
        }
        throw new Error('Failed to create work item');
      }

      const data = await response.json();
      return data.workItem;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['work-items'] });
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

export function useUpdateWorkItem() {
  const authStore = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      updates,
    }: {
      id: number | string;
      updates: Partial<WorkItem>;
    }): Promise<WorkItem> => {
      const response = await fetch(`${API_URL}/api/work-items/${id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.token}`,
        },
        body: JSON.stringify(updates),
      });

      if (!response.ok) {
        if (response.status === 401) {
          authStore.logout();
        }
        throw new Error('Failed to update work item');
      }

      const data = await response.json();
      return data.workItem;
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['work-items'] });
      queryClient.invalidateQueries({ queryKey: ['work-item', id] });
    },
  });
}

export function useDeleteWorkItem() {
  const authStore = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number | string): Promise<void> => {
      const response = await fetch(`${API_URL}/api/work-items/${id}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          authStore.logout();
        }
        throw new Error('Failed to delete work item');
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['work-items'] });
    },
  });
}
