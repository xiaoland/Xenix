/**
 * Datasets Composable
 * Uses TanStack Query with Hono RPC client for type-safe data fetching
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query';

import { client } from '../api/client';
import { API_CONFIG } from '../constants/config';

export function useDatasets() {
  return useQuery({
    queryKey: ['datasets'],
    queryFn: async () => {
      const response = await client.data.$get({});
      if (!response.ok) {
        throw new Error('Failed to fetch datasets');
      }
      return response.json();
    },
  });
}

export function useDataset(id: number | string) {
  return useQuery({
    queryKey: ['dataset', id],
    queryFn: async () => {
      const response = await client.data[':id'].$get({
        param: { id: String(id) },
      });
      if (!response.ok) {
        throw new Error('Failed to fetch dataset');
      }
      return response.json();
    },
    enabled: !!id,
  });
}

export function useUploadDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (formData: FormData) => {
      // Use fetch directly for FormData to ensure proper Content-Type with boundary
      const token = localStorage.getItem('auth_token');
      const apiUrl = import.meta.env.VITE_API_URL || API_CONFIG.DEFAULT_URL;

      const response = await fetch(`${apiUrl}/data`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          // Don't set Content-Type - let browser set it with boundary
        },
        body: formData,
      });

      if (!response.ok) {
        const error = (await response.json()) as any;
        throw new Error(error.error || 'Failed to upload dataset');
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
    },
  });
}

export function useDeleteDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number | string) => {
      const response = await client.data[':id'].$delete({
        param: { id: String(id) },
      });
      if (!response.ok) {
        throw new Error('Failed to delete dataset');
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
    },
  });
}
