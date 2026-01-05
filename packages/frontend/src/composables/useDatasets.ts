/**
 * Datasets Composable
 * Uses TanStack Query for data fetching and caching
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { useAuthStore } from '../stores/auth';
import type { Dataset } from '@xenix/shared';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000';

export function useDatasets() {
  const authStore = useAuthStore();

  return useQuery({
    queryKey: ['datasets'],
    queryFn: async (): Promise<Dataset[]> => {
      const response = await fetch(`${API_URL}/api/data`, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          authStore.logout();
        }
        throw new Error('Failed to fetch datasets');
      }

      const data = await response.json();
      return data.datasets || [];
    },
    enabled: authStore.isAuthenticated,
  });
}

export function useDataset(id: number | string) {
  const authStore = useAuthStore();

  return useQuery({
    queryKey: ['dataset', id],
    queryFn: async (): Promise<Dataset> => {
      const response = await fetch(`${API_URL}/api/data/${id}`, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authStore.token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          authStore.logout();
        }
        throw new Error('Failed to fetch dataset');
      }

      const data = await response.json();
      return data.dataset;
    },
    enabled: authStore.isAuthenticated && !!id,
  });
}

export function useUploadDataset() {
  const authStore = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (formData: FormData): Promise<Dataset> => {
      const response = await fetch(`${API_URL}/api/data`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authStore.token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        if (response.status === 401) {
          authStore.logout();
        }
        throw new Error('Failed to upload dataset');
      }

      const data = await response.json();
      return data.dataset;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
    },
  });
}

export function useDeleteDataset() {
  const authStore = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number | string): Promise<void> => {
      const response = await fetch(`${API_URL}/api/data/${id}`, {
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
        throw new Error('Failed to delete dataset');
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
    },
  });
}
