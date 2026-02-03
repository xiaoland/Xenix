/**
 * Datasets Queries
 * TanStack Query hooks for dataset data fetching
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query';
import { MaybeRef, unref } from 'vue';

import { client } from '@/services/api-client';
import { API_CONFIG } from '@/constants/config';

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

export function useDataset(id?: MaybeRef<number | string | undefined>) {
  return useQuery({
    queryKey: ['dataset', id],
    queryFn: async () => {
      const response = await client.data[':id'].$get({
        param: { id: String(unref(id)) },
      });
      if (!response.ok) {
        throw new Error('Failed to fetch dataset');
      }
      return response.json();
    },
    enabled: !!unref(id),
  });
}

export function useUploadDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (params: {
      file: File;
      name: string;
      projectId: number;
    }) => {
      const formData = new FormData();
      formData.append('file', params.file);
      formData.append('name', params.name);
      formData.append('projectId', params.projectId.toString());

      const token = localStorage.getItem('auth_token');
      const apiUrl = import.meta.env.VITE_API_URL || API_CONFIG.DEFAULT_URL;

      const response = await fetch(`${apiUrl}/data/upload`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error((error as any).error || 'Failed to upload dataset');
      }

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
    },
  });
}

export function useCreateDataset() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (params: {
      name: string;
      projectId: number;
      storage: 'local' | 'oss';
      filePath: string;
      file: File | null;
      columns: string[];
      rowCount: number;
      fileSize: number;
    }) => {
      if (params.storage === 'oss' && !params.file) {
        throw new Error('File is required for OSS storage');
      }

      if (params.storage === 'oss' && params.file) {
        const formData = new FormData();
        formData.append('file', params.file);
        formData.append('name', params.name);
        formData.append('projectId', params.projectId.toString());

        const token = localStorage.getItem('auth_token');
        const apiUrl = import.meta.env.VITE_API_URL || API_CONFIG.DEFAULT_URL;

        const response = await fetch(`${apiUrl}/data/upload`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error((error as any).error || 'Failed to upload dataset');
        }

        return response.json();
      }

      const confirmResponse = await client.data['confirm-upload'].$post({
        json: {
          key: params.filePath,
          name: params.name,
          projectId: params.projectId,
          fileSize: params.fileSize,
          columns: params.columns,
          rowCount: params.rowCount,
          storage: params.storage,
        },
      });

      if (!confirmResponse.ok) {
        const error = await confirmResponse.json();
        throw new Error((error as any).error || 'Failed to create dataset');
      }

      return confirmResponse.json();
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
